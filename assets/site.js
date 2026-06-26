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

    /* ----- 기사 Q&A: FAB + 드래그 선택 질문 + 패널, 기기당 일일 한도 ----- */
    var amEl = document.querySelector('meta[name="ask-endpoint"]');
    var askEndpoint = amEl ? (amEl.getAttribute('content') || '') : '';
    var enabled = !!askEndpoint;
    var askFab = overlay.querySelector('.ask-fab');
    var askPanel = overlay.querySelector('.ask-panel');
    var askInput = overlay.querySelector('.ask-input');
    var askSend = overlay.querySelector('.ask-send');
    var askAnswer = overlay.querySelector('.ask-answer');
    var askQuote = overlay.querySelector('.ask-quote');
    var askCountEl = overlay.querySelector('.ask-count');
    var askX = overlay.querySelector('.ask-x');
    var selAsk = document.querySelector('.sel-ask');
    var selBtn = selAsk ? selAsk.querySelector('.sel-ask-btn') : null;
    var asking = false, selectedText = '';
    var ASK_LIMIT = 50;

    function todayKey() { var d = new Date(); return 'ask:' + d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate(); }
    function getCount() { try { return parseInt(localStorage.getItem(todayKey()) || '0', 10) || 0; } catch (e) { return 0; } }
    function bumpCount() { try { localStorage.setItem(todayKey(), String(getCount() + 1)); } catch (e) {} }
    function updateCount() {
      var left = Math.max(0, ASK_LIMIT - getCount());
      if (askCountEl) askCountEl.textContent = '오늘 남은 질문 ' + left + '/' + ASK_LIMIT + ' · 이 기기 기준';
      var out = left <= 0;
      if (askInput) { askInput.disabled = out; if (out) askInput.placeholder = '오늘 질문 한도를 다 썼어요'; }
      if (askSend) askSend.disabled = out || asking;
    }
    function hideSel() { if (selAsk) selAsk.hidden = true; }
    function setQuote(t) {
      selectedText = t || '';
      if (!askQuote) return;
      if (selectedText) { askQuote.hidden = false; askQuote.textContent = '“' + selectedText.slice(0, 140) + (selectedText.length > 140 ? '…' : '') + '”'; }
      else { askQuote.hidden = true; askQuote.textContent = ''; }
    }
    function openPanel() { if (!enabled || !askPanel) return; askPanel.hidden = false; updateCount(); setTimeout(function () { if (askInput && !askInput.disabled) askInput.focus(); }, 50); }
    function closePanel() { if (askPanel) askPanel.hidden = true; hideSel(); }
    function askReset() {
      asking = false; setQuote('');
      if (askInput) { askInput.value = ''; askInput.disabled = false; askInput.placeholder = '이 기사에서 궁금한 점'; }
      if (askAnswer) { askAnswer.hidden = true; askAnswer.textContent = ''; askAnswer.classList.remove('err'); }
      if (askPanel) askPanel.hidden = true;
      hideSel();
      if (askFab) askFab.hidden = !enabled;
      updateCount();
    }
    function doAsk() {
      if (asking || !enabled || !curItem) return;
      if (getCount() >= ASK_LIMIT) { updateCount(); return; }
      var q = (askInput.value || '').trim();
      if (!q) return;
      asking = true; askSend.disabled = true;
      askAnswer.hidden = false; askAnswer.classList.remove('err'); askAnswer.textContent = '답변 생성 중…';
      var ctx = '';
      (curItem.content || []).forEach(function (b) { if (b.text) ctx += b.text + '\n'; });
      if (!ctx) ctx = curItem.blurb || '';
      fetch(askEndpoint, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, title: curItem.title || '', context: ctx.slice(0, 8000), selection: selectedText.slice(0, 500) })
      }).then(function (r) { return r.json(); })
        .then(function (j) { askAnswer.textContent = (j && j.answer) ? j.answer : '답변을 받지 못했어요.'; bumpCount(); })
        .catch(function () { askAnswer.textContent = '오류가 났어요. 잠시 후 다시 시도해 주세요.'; askAnswer.classList.add('err'); })
        .then(function () { asking = false; updateCount(); });
    }
    if (askFab) askFab.addEventListener('click', function () { setQuote(''); openPanel(); });
    if (askX) askX.addEventListener('click', closePanel);
    if (askSend) askSend.addEventListener('click', doAsk);
    if (askInput) askInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') doAsk(); });
    if (enabled && bodyEl) {
      bodyEl.addEventListener('mouseup', function () {
        setTimeout(function () {
          var sel = window.getSelection(); var t = sel ? String(sel) : '';
          if (t && t.trim().length >= 2 && sel.anchorNode && bodyEl.contains(sel.anchorNode)) {
            var rect = sel.getRangeAt(0).getBoundingClientRect();
            selAsk.style.left = Math.min(window.innerWidth - 96, Math.max(8, rect.left + rect.width / 2 - 44)) + 'px';
            selAsk.style.top = Math.max(8, rect.top - 46) + 'px';
            selAsk.hidden = false; selAsk._text = t.trim();
          } else { hideSel(); }
        }, 10);
      });
    }
    if (selBtn) selBtn.addEventListener('click', function () { setQuote(selAsk._text || ''); hideSel(); openPanel(); });
    window.addEventListener('scroll', hideSel, true);

    function open(idx) {
      var it = items[idx];
      if (!it) return;
      curItem = it; ttsReset(); askReset();
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
      ttsReset(); closePanel();
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

  /* ---------- 5) 뉴스 검색: 본문 포함 + 가중 랭킹 + 스니펫 (search.json 지연 로드) ---------- */
  function initSearch() {
    var input = document.getElementById('news-search');
    var results = document.getElementById('search-results');
    var feed = document.getElementById('feed');
    var clearBtn = document.getElementById('search-clear');
    if (!input || !results || !feed) return;
    var srcUrl = input.getAttribute('data-index') || 'search.json';
    var items = null, loading = false, pending = null;

    function esc(s) {
      return String(s).replace(/[&<>"]/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
      });
    }
    function escRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
    function highlight(text, terms) {
      var out = esc(text);
      terms.forEach(function (t) { if (t) out = out.replace(new RegExp('(' + escRe(esc(t)) + ')', 'gi'), '<mark>$1</mark>'); });
      return out;
    }
    function snippet(c, terms) {
      if (!c) return '';
      var lc = c.toLowerCase(), pos = -1;
      terms.forEach(function (t) { var i = lc.indexOf(t); if (i >= 0 && (pos < 0 || i < pos)) pos = i; });
      if (pos < 0) return '';
      var start = Math.max(0, pos - 40), end = Math.min(c.length, pos + 110);
      return (start > 0 ? '…' : '') + highlight(c.slice(start, end), terms) + (end < c.length ? '…' : '');
    }
    function load(cb) {
      if (items) { cb(); return; }
      if (loading) { pending = cb; return; }
      loading = true;
      fetch(srcUrl).then(function (r) { return r.json(); }).then(function (j) {
        items = j; loading = false; cb(); if (pending) { var p = pending; pending = null; p(); }
      }).catch(function () {
        loading = false;
        results.innerHTML = '<p class="search-empty">검색 데이터를 불러오지 못했습니다.</p>';
      });
    }
    function render(q) {
      var ql = q.trim().toLowerCase();
      clearBtn.hidden = !q;
      if (!ql) { results.hidden = true; results.innerHTML = ''; feed.hidden = false; return; }
      feed.hidden = true; results.hidden = false;
      if (!items) {
        results.innerHTML = '<p class="search-empty">검색 준비 중…</p>';
        load(function () { if (input.value.trim().toLowerCase() === ql) render(q); });
        return;
      }
      var terms = ql.split(/\s+/).filter(Boolean);
      var scored = [];
      items.forEach(function (it) {
        var T = (it.t || '').toLowerCase(), B = (it.b || '').toLowerCase(),
            S = (it.s || '').toLowerCase(), C = (it.c || '').toLowerCase(), D = (it.d || '').toLowerCase();
        var ok = true, score = 0;
        for (var k = 0; k < terms.length; k++) {
          var t = terms[k];
          if (T.indexOf(t) < 0 && B.indexOf(t) < 0 && S.indexOf(t) < 0 && C.indexOf(t) < 0 && D.indexOf(t) < 0) { ok = false; break; }
          score += (T.indexOf(t) >= 0 ? 5 : 0) + (B.indexOf(t) >= 0 ? 3 : 0) + (S.indexOf(t) >= 0 ? 2 : 0) + (C.split(t).length - 1);
        }
        if (ok) scored.push({ it: it, score: score });
      });
      scored.sort(function (a, b) { return b.score - a.score; });
      if (!scored.length) { results.innerHTML = '<p class="search-empty">“' + esc(q) + '” 검색 결과가 없습니다.</p>'; return; }
      var html = '<div class="search-count">' + scored.length + '건</div>';
      scored.forEach(function (o) {
        var it = o.it, href = 'days/' + it.id + '.html?n=' + it.n;
        var thumb = it.img ? '<img class="sr-thumb" src="' + esc(it.img) + '" alt="" loading="lazy" onerror="this.remove()">' : '';
        var snip = snippet(it.c, terms) || esc(it.b || '');
        html += '<a class="sr-item" href="' + href + '">' + thumb +
          '<div class="sr-text"><div class="sr-meta">' + esc(it.s) + ' · ' + esc(it.d) +
          (it.wd ? (' (' + esc(it.wd) + ')') : '') + '</div>' +
          '<div class="sr-title">' + highlight(it.t, terms) + '</div>' +
          (snip ? ('<div class="sr-blurb">' + snip + '</div>') : '') + '</div></a>';
      });
      results.innerHTML = html;
    }
    input.addEventListener('input', function () { render(input.value); });
    clearBtn.addEventListener('click', function () { input.value = ''; render(''); input.focus(); });
    input.addEventListener('focus', function () { load(function () {}); }, { once: true });
    var q0 = new URLSearchParams(location.search).get('q');
    if (q0) { input.value = q0; render(q0); }
  }

  /* ---------- 6) 새 빌드 자동 감지 (강제 새로고침 불필요) ---------- */
  function initUpdateCheck() {
    var meta = document.querySelector('meta[name="site-build"]');
    if (!meta) return;
    var cur = meta.getAttribute('content') || '';
    var src = meta.getAttribute('data-src') || 'build.json';
    if (!cur) return;
    var toasted = false;
    function toast(v) {
      if (toasted) return; toasted = true;
      var el = document.createElement('div');
      el.className = 'update-toast';
      el.innerHTML = '새 글이 업데이트됐어요 <button type="button">새로고침</button>';
      el.querySelector('button').addEventListener('click', function () {
        location.replace(location.pathname + '?_=' + v);
      });
      document.body.appendChild(el);
      requestAnimationFrame(function () { el.classList.add('show'); });
    }
    function check(initial) {
      fetch(src + '?_=' + Date.now(), { cache: 'no-store' })
        .then(function (r) { return r.json(); })
        .then(function (j) {
          if (!j || !j.v || j.v === cur) return;
          var key = 'rl:' + j.v;
          var seen = false;
          try { seen = !!sessionStorage.getItem(key); } catch (e) {}
          if (initial && !seen) {
            try { sessionStorage.setItem(key, '1'); } catch (e) {}
            location.replace(location.pathname + '?_=' + j.v);   // 캐시 무시 새로고침
          } else {
            toast(j.v);
          }
        }).catch(function () {});
    }
    check(true);
    document.addEventListener('visibilitychange', function () { if (!document.hidden) check(false); });
    setInterval(function () { check(false); }, 300000);
  }

  function boot() { initQuiz(); initNews(); initSearch(); initUpdateCheck(); }
  if (document.readyState !== 'loading') boot();
  else document.addEventListener('DOMContentLoaded', boot);
})();
