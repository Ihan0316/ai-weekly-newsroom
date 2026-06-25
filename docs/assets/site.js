/* 주간 AI 뉴스룸 — 공유 인터랙션
   1) 카드/스토리 3D 포인터 틸트
   2) 히어로 Three.js 미니멀 회전 다면체 (#scene, 인덱스에만)
   reduced-motion 존중, three 로드 실패 시 graceful (CSS 폴백) */
(function () {
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var coarse = window.matchMedia && window.matchMedia('(hover: none), (pointer: coarse)').matches;

  /* ---------- 1) tilt (포인터 기기만; 터치/모바일 제외) ---------- */
  function initTilt() {
    if (reduce || coarse) return;
    var els = document.querySelectorAll('.tilt');
    els.forEach(function (el) {
      var max = el.classList.contains('featured-tilt') ? 5 : 7;
      el.addEventListener('pointermove', function (e) {
        var r = el.getBoundingClientRect();
        var px = (e.clientX - r.left) / r.width - 0.5;
        var py = (e.clientY - r.top) / r.height - 0.5;
        el.style.setProperty('--ry', (px * max).toFixed(2) + 'deg');
        el.style.setProperty('--rx', (-py * max).toFixed(2) + 'deg');
      });
      el.addEventListener('pointerleave', function () {
        el.style.setProperty('--ry', '0deg');
        el.style.setProperty('--rx', '0deg');
      });
    });
  }

  /* ---------- 2) three.js hero ---------- */
  function initHero() {
    var canvas = document.getElementById('scene');
    if (!canvas || typeof THREE === 'undefined') return; // CSS fallback stays
    var host = canvas.parentElement;
    var w = host.clientWidth, h = host.clientHeight;
    var renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true });
    renderer.setSize(w, h, false);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, window.innerWidth < 700 ? 1.5 : 2));

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(38, w / h, 0.1, 100);
    camera.position.set(0, 0, 6);

    var css = getComputedStyle(document.documentElement);
    var accent = (css.getPropertyValue('--accent') || '#c2532f').trim();
    var ink = (css.getPropertyValue('--ink') || '#191711').trim();

    var geo = new THREE.IcosahedronGeometry(1.85, 0); // low-poly, faceted
    var mat = new THREE.MeshStandardMaterial({
      color: new THREE.Color(accent), metalness: 0.18, roughness: 0.42, flatShading: true
    });
    var mesh = new THREE.Mesh(geo, mat);
    scene.add(mesh);

    // thin wireframe overlay for editorial line quality
    var wire = new THREE.LineSegments(
      new THREE.WireframeGeometry(geo),
      new THREE.LineBasicMaterial({ color: new THREE.Color(ink), transparent: true, opacity: 0.18 })
    );
    wire.scale.setScalar(1.005);
    scene.add(wire);

    scene.add(new THREE.AmbientLight(0xffffff, 0.55));
    var key = new THREE.DirectionalLight(0xffffff, 1.15); key.position.set(4, 5, 6); scene.add(key);
    var rim = new THREE.DirectionalLight(new THREE.Color(accent), 0.6); rim.position.set(-6, -2, -3); scene.add(rim);

    var px = 0, py = 0;
    window.addEventListener('pointermove', function (e) {
      px = (e.clientX / window.innerWidth - 0.5);
      py = (e.clientY / window.innerHeight - 0.5);
    });

    var t = 0;
    function frame() {
      t += 0.0045;
      var ry = reduce ? 0 : t;
      mesh.rotation.y = ry + px * 0.5; mesh.rotation.x = 0.25 + py * 0.4;
      wire.rotation.copy(mesh.rotation);
      mesh.position.y = reduce ? 0 : Math.sin(t * 1.4) * 0.12;
      wire.position.copy(mesh.position);
      renderer.render(scene, camera);
      requestAnimationFrame(frame);
    }
    frame();

    window.addEventListener('resize', function () {
      var nw = host.clientWidth, nh = host.clientHeight;
      camera.aspect = nw / nh; camera.updateProjectionMatrix();
      renderer.setSize(nw, nh, false);
    });
  }

  /* ---------- 3) 정처기 퀴즈: 클릭 시 정답/오답 ---------- */
  function initQuiz() {
    document.querySelectorAll('.quiz').forEach(function (quiz) {
      var answer = parseInt(quiz.getAttribute('data-answer'), 10);
      quiz.querySelectorAll('.qopt').forEach(function (opt) {
        opt.addEventListener('click', function () {
          if (quiz.classList.contains('answered')) return;
          quiz.classList.add('answered');
          var i = parseInt(opt.getAttribute('data-i'), 10);
          var correct = quiz.querySelector('.qopt[data-i="' + answer + '"]');
          if (i === answer) {
            opt.classList.add('is-correct');
            opt.querySelector('.qmark').textContent = '✓';
          } else {
            opt.classList.add('is-wrong');
            opt.querySelector('.qmark').textContent = '✗';
            if (correct) {
              correct.classList.add('is-correct');
              correct.querySelector('.qmark').textContent = '✓';
            }
          }
          var ex = quiz.querySelector('.q-explain');
          if (ex) ex.hidden = false;
        });
      });
    });
  }

  /* ---------- 4) 뉴스 원문 3D 모달 ---------- */
  function initNews() {
    var dataEl = document.getElementById('news-data');
    var overlay = document.getElementById('news-modal');
    if (!dataEl || !overlay) return;
    var items = [];
    try { items = JSON.parse(dataEl.textContent || '[]'); } catch (e) { items = []; }
    var titleEl = overlay.querySelector('.modal-title');
    var srcEl = overlay.querySelector('.modal-src');
    var bodyEl = overlay.querySelector('.modal-body');
    var origEl = overlay.querySelector('.modal-orig');
    var heroEl = overlay.querySelector('.modal-hero');
    var closeBtn = overlay.querySelector('.modal-close');
    if (heroEl) heroEl.onerror = function () { heroEl.hidden = true; };
    var lastFocus = null;

    /* ----- TTS: 뉴럴 MP3(있으면) 우선, 없으면 브라우저 음성 폴백 ----- */
    var synth = window.speechSynthesis;
    var ttsBtn = overlay.querySelector('.tts-toggle');
    var ttsState = 'idle';   // idle | playing | paused
    var usingAudio = false;
    var koVoice = null;
    var curItem = null;
    var audioEl = (typeof Audio !== 'undefined') ? new Audio() : null;
    if (audioEl) {
      audioEl.preload = 'none';
      audioEl.addEventListener('ended', function () { ttsState = 'idle'; ttsUI('idle'); });
      audioEl.addEventListener('error', function () { if (usingAudio) { ttsState = 'idle'; ttsUI('idle'); } });
    }
    function ttsUI(state) {
      if (!ttsBtn) return;
      var ico = ttsBtn.querySelector('.tts-ico'), lab = ttsBtn.querySelector('.tts-label');
      if (state === 'playing') { ico.textContent = '⏸'; lab.textContent = '일시정지'; ttsBtn.classList.add('on'); }
      else if (state === 'paused') { ico.textContent = '▶'; lab.textContent = '이어 듣기'; ttsBtn.classList.add('on'); }
      else { ico.textContent = '🔊'; lab.textContent = '본문 듣기'; ttsBtn.classList.remove('on'); }
    }
    if (ttsBtn && (synth || audioEl)) {
      ttsBtn.hidden = false;
      if (synth) {
        var pickVoice = function () {
          var vs = synth.getVoices() || [];
          var ko = vs.filter(function (v) { return /ko/i.test(v.lang); });
          // 여성 보이스 우선(이름 힌트) → 그다음 Google/Neural 고품질 → 나머지
          var female = ko.filter(function (v) { return /female|여성|sunhi|sun-?hi|heami|yuna|nari|jimin|ji-?min|seo|yujin|소|선희|아라|유나/i.test(v.name); });
          var pool = female.length ? female : ko;
          koVoice = pool.filter(function (v) { return /google|neural|natural/i.test(v.name); })[0] || pool[0] || null;
        };
        pickVoice();
        try { synth.onvoiceschanged = pickVoice; } catch (e) {}
      }
    }
    function ttsReset() {
      if (synth) synth.cancel();
      if (audioEl) { try { audioEl.pause(); audioEl.currentTime = 0; } catch (e) {} }
      ttsState = 'idle'; ttsUI('idle');
    }
    function ttsTextOf(it) {
      var parts = [];
      if (it.title) parts.push(it.title);
      (it.content || []).forEach(function (b) { if (b.text) parts.push(b.text); });
      if (!parts.length && it.blurb) parts.push(it.blurb);
      return parts.join('.\n');
    }
    function ttsStart() {
      if (!curItem) return;
      if (curItem.audio && audioEl) {
        usingAudio = true;
        audioEl.src = curItem.audio;
        var p = audioEl.play();
        if (p && p.catch) p.catch(function () { ttsState = 'idle'; ttsUI('idle'); });
      } else if (synth) {
        usingAudio = false;
        synth.cancel();
        var u = new SpeechSynthesisUtterance(ttsTextOf(curItem));
        u.lang = 'ko-KR'; if (koVoice) u.voice = koVoice; u.rate = 1.0;
        u.onend = function () { ttsState = 'idle'; ttsUI('idle'); };
        u.onerror = function () { ttsState = 'idle'; ttsUI('idle'); };
        synth.speak(u);
      } else { return; }
      ttsState = 'playing'; ttsUI('playing');
    }
    if (ttsBtn) ttsBtn.addEventListener('click', function () {
      if (ttsState === 'idle') ttsStart();
      else if (ttsState === 'playing') {
        if (usingAudio && audioEl) audioEl.pause(); else if (synth) synth.pause();
        ttsState = 'paused'; ttsUI('paused');
      } else if (ttsState === 'paused') {
        if (usingAudio && audioEl) audioEl.play(); else if (synth) synth.resume();
        ttsState = 'playing'; ttsUI('playing');
      }
    });

    function open(idx) {
      var it = items[idx];
      if (!it) return;
      curItem = it; ttsReset();
      lastFocus = document.activeElement;
      titleEl.textContent = it.title || '';
      srcEl.textContent = it.source || '';
      origEl.href = it.url || '#';
      if (heroEl) {
        if (it.image) { heroEl.hidden = false; heroEl.src = it.image; }
        else { heroEl.hidden = true; heroEl.removeAttribute('src'); }
      }
      bodyEl.innerHTML = '';
      if (it.content && it.content.length) {
        var t = (it.title || '').trim();
        it.content.forEach(function (b, i) {
          // 첫 소제목이 기사 제목과 같으면 중복이라 건너뜀
          if (i === 0 && b.t === 'h' && (b.text || '').trim() === t) return;
          var el = document.createElement(b.t === 'h' ? 'h3' : 'p');
          el.textContent = b.text;
          bodyEl.appendChild(el);
        });
      } else {
        if (it.blurb) {
          var p = document.createElement('p');
          p.className = 'mb-blurb'; p.textContent = it.blurb; bodyEl.appendChild(p);
        }
        var n = document.createElement('div');
        n.className = 'mb-note';
        n.textContent = '원문 본문은 아직 준비 중입니다. 아래 링크에서 원문을 확인하세요.';
        bodyEl.appendChild(n);
      }
      overlay.hidden = false;
      overlay.classList.add('open');            // display:flex 즉시 (rAF 비의존)
      var showIt = function () { overlay.classList.add('show'); };
      requestAnimationFrame(showIt);
      setTimeout(showIt, 30);                   // 백그라운드 탭 등 rAF 미작동 시 폴백
      document.body.style.overflow = 'hidden';
      bodyEl.parentElement.scrollTop = 0;
      if (closeBtn) closeBtn.focus();
    }
    function close() {
      if (overlay.hidden) return;
      ttsReset();
      overlay.classList.remove('show');
      var done = function () {
        if (overlay.hidden) return;
        overlay.classList.remove('open');
        overlay.hidden = true;
        document.body.style.overflow = '';
        if (lastFocus && lastFocus.focus) lastFocus.focus();
      };
      var t = setTimeout(done, 480);
      overlay.addEventListener('transitionend', function te() {
        clearTimeout(t); overlay.removeEventListener('transitionend', te); done();
      });
    }
    document.querySelectorAll('.newsitem').forEach(function (btn) {
      btn.addEventListener('click', function () {
        open(parseInt(btn.getAttribute('data-idx'), 10));
      });
    });
    overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });
    if (closeBtn) closeBtn.addEventListener('click', close);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !overlay.hidden) close();
    });
    // 검색 결과에서 들어온 경우 해당 기사 모달 자동 오픈 (?n=)
    var n0 = new URLSearchParams(location.search).get('n');
    if (n0 !== null) { var ni = parseInt(n0, 10); if (!isNaN(ni)) open(ni); }
  }

  /* ---------- 5) 뉴스 검색 (인덱스 페이지) ---------- */
  function initSearch() {
    var input = document.getElementById('news-search');
    var results = document.getElementById('search-results');
    var feed = document.getElementById('feed');
    var clearBtn = document.getElementById('search-clear');
    var dataEl = document.getElementById('search-index');
    if (!input || !results || !feed || !dataEl) return;
    var items = [];
    try { items = JSON.parse(dataEl.textContent || '[]'); } catch (e) { items = []; }
    function esc(s) {
      return String(s).replace(/[&<>"]/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
      });
    }
    function render(q) {
      var ql = q.trim().toLowerCase();
      clearBtn.hidden = !q;
      if (!ql) { results.hidden = true; results.innerHTML = ''; feed.hidden = false; return; }
      var terms = ql.split(/\s+/).filter(Boolean);
      var hits = items.filter(function (it) {
        var hay = (it.t + ' ' + it.b + ' ' + it.s + ' ' + it.d).toLowerCase();
        return terms.every(function (t) { return hay.indexOf(t) >= 0; });
      });
      feed.hidden = true; results.hidden = false;
      if (!hits.length) {
        results.innerHTML = '<p class="search-empty">“' + esc(q) + '” 검색 결과가 없습니다.</p>';
        return;
      }
      var html = '<div class="search-count">' + hits.length + '건</div>';
      hits.forEach(function (it) {
        var href = 'days/' + it.id + '.html?n=' + it.n;
        var thumb = it.img ? '<img class="sr-thumb" src="' + esc(it.img) + '" alt="" loading="lazy" onerror="this.remove()">' : '';
        html += '<a class="sr-item" href="' + href + '">' + thumb +
          '<div class="sr-text"><div class="sr-meta">' + esc(it.s) + ' · ' + esc(it.d) +
          (it.wd ? (' (' + esc(it.wd) + ')') : '') + '</div>' +
          '<div class="sr-title">' + esc(it.t) + '</div>' +
          (it.b ? ('<div class="sr-blurb">' + esc(it.b) + '</div>') : '') + '</div></a>';
      });
      results.innerHTML = html;
    }
    input.addEventListener('input', function () { render(input.value); });
    clearBtn.addEventListener('click', function () { input.value = ''; render(''); input.focus(); });
    var q0 = new URLSearchParams(location.search).get('q');
    if (q0) { input.value = q0; render(q0); }
  }

  function boot() { initTilt(); initHero(); initQuiz(); initNews(); initSearch(); }
  if (document.readyState !== 'loading') boot();
  else document.addEventListener('DOMContentLoaded', boot);
})();
