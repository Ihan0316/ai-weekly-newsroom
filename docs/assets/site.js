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
    var closeBtn = overlay.querySelector('.modal-close');
    var lastFocus = null;

    function open(idx) {
      var it = items[idx];
      if (!it) return;
      lastFocus = document.activeElement;
      titleEl.textContent = it.title || '';
      srcEl.textContent = it.source || '';
      origEl.href = it.url || '#';
      bodyEl.innerHTML = '';
      if (it.content && it.content.length) {
        it.content.forEach(function (b) {
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
  }

  function boot() { initTilt(); initHero(); initQuiz(); initNews(); }
  if (document.readyState !== 'loading') boot();
  else document.addEventListener('DOMContentLoaded', boot);
})();
