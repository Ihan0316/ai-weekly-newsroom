/* 주간 AI 뉴스룸 — 공유 인터랙션
   1) 카드/스토리 3D 포인터 틸트
   2) 히어로 Three.js 미니멀 회전 다면체 (#scene, 인덱스에만)
   reduced-motion 존중, three 로드 실패 시 graceful (CSS 폴백) */
(function () {
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- 1) tilt ---------- */
  function initTilt() {
    if (reduce) return;
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
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

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

  function boot() { initTilt(); initHero(); }
  if (document.readyState !== 'loading') boot();
  else document.addEventListener('DOMContentLoaded', boot);
})();
