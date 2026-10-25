/* Hostel Management System - shared front-end behaviour + motion system */
(function () {
  "use strict";

  var prefersReducedMotion =
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  // ---------------------------------------------------------------- Sidebar
  function initSidebar() {
    var sidebar = document.querySelector(".hms-sidebar");
    if (!sidebar) return;
    var toggle = document.querySelector(".sidebar-toggle");
    var closeBtn = document.getElementById("hms-sidebar-close");
    var backdrop = document.createElement("div");
    backdrop.className = "hms-backdrop";
    document.body.appendChild(backdrop);

    function openSidebar() {
      sidebar.classList.add("open");
      backdrop.classList.add("show");
      if (toggle) toggle.setAttribute("aria-expanded", "true");
      if (closeBtn) closeBtn.focus();
    }
    function closeSidebar() {
      sidebar.classList.remove("open");
      backdrop.classList.remove("show");
      if (toggle) {
        toggle.setAttribute("aria-expanded", "false");
        if (sidebar.contains(document.activeElement)) toggle.focus();
      }
    }

    if (toggle) {
      toggle.setAttribute("aria-controls", sidebar.id || "hms-sidebar");
      toggle.setAttribute("aria-expanded", "false");
      toggle.addEventListener("click", function () {
        if (sidebar.classList.contains("open")) closeSidebar();
        else openSidebar();
      });
    }
    if (closeBtn) closeBtn.addEventListener("click", closeSidebar);
    backdrop.addEventListener("click", closeSidebar);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && sidebar.classList.contains("open")) closeSidebar();
    });
  }

  // -------------------------------------------------------- Page transitions
  function initPageTransitions() {
    if (prefersReducedMotion) return;

    document.addEventListener("click", function (e) {
      if (e.defaultPrevented || e.button !== 0) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

      var link = e.target.closest && e.target.closest("a[href]");
      if (!link) return;
      if (link.target && link.target !== "_self") return;
      if (link.hasAttribute("download")) return;
      if (link.dataset && link.dataset.noTransition !== undefined) return;
      if (link.rel && link.rel.indexOf("external") !== -1) return;

      var href = link.getAttribute("href");
      if (!href || href.charAt(0) === "#") return;
      if (/^(mailto:|tel:|javascript:)/i.test(href)) return;

      var url;
      try {
        url = new URL(link.href, window.location.href);
      } catch (err) {
        return;
      }
      if (url.origin !== window.location.origin) return;
      if (
        url.pathname === window.location.pathname &&
        url.search === window.location.search
      ) {
        return;
      }

      e.preventDefault();
      document.body.classList.add("hms-leaving");
      window.setTimeout(function () {
        window.location.href = url.href;
      }, 200);
    });

    window.addEventListener("pageshow", function () {
      document.body.classList.remove("hms-leaving");
    });
  }

  // ------------------------------------------------------------- Scroll reveal
  function initReveal() {
    var items = document.querySelectorAll("[data-reveal]");
    if (!items.length) return;

    if (prefersReducedMotion || !("IntersectionObserver" in window)) {
      items.forEach(function (el) {
        el.classList.add("is-visible");
      });
      return;
    }

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.06 }
    );
    items.forEach(function (el) {
      observer.observe(el);
    });
  }

  // --------------------------------------------------- Misc shared behaviour
  function initWidgets() {
    document.querySelectorAll("[data-auto-submit]").forEach(function (el) {
      el.addEventListener("change", function () {
        var form = el.closest("form");
        if (form) form.submit();
      });
    });

    document.querySelectorAll("[data-confirm]").forEach(function (el) {
      el.addEventListener("click", function (event) {
        if (!window.confirm(el.getAttribute("data-confirm"))) {
          event.preventDefault();
          event.stopPropagation();
        }
      });
    });

    document.querySelectorAll(".alert-auto-dismiss").forEach(function (el) {
      window.setTimeout(function () {
        if (window.bootstrap && window.bootstrap.Alert) {
          window.bootstrap.Alert.getOrCreateInstance(el).close();
        } else {
          el.style.display = "none";
        }
      }, 6000);
    });

    if (window.bootstrap && window.bootstrap.Tooltip) {
      document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
        new window.bootstrap.Tooltip(el);
      });
    }
  }

  // ------------------------------------------------ Lazy Three.js auth hero
  // Restrained, monochrome architectural wireframe. Loaded only on the auth
  // pages, only when WebGL is available and motion is allowed. Fully disposed
  // on unload. Falls back to the static graphite background otherwise.
  function initAuthHero() {
    var canvas = document.querySelector("[data-hms-hero]");
    if (!canvas || prefersReducedMotion) return;

    function hasWebGL() {
      try {
        var c = document.createElement("canvas");
        return !!(c.getContext("webgl") || c.getContext("experimental-webgl"));
      } catch (err) {
        return false;
      }
    }
    if (!hasWebGL()) return;

    var THREE_URL = "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";
    import(/* webpackIgnore: true */ THREE_URL)
      .then(function (THREE) {
        buildHero(THREE, canvas);
      })
      .catch(function () {
        /* offline / blocked: keep the static fallback */
      });
  }

  function buildHero(THREE, canvas) {
    var parent = canvas.parentElement;
    var width = parent.clientWidth;
    var height = parent.clientHeight;

    var renderer = new THREE.WebGLRenderer({
      canvas: canvas,
      antialias: true,
      alpha: true,
      powerPreference: "low-power",
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.setSize(width, height, false);

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.set(0, 2.2, 9);
    camera.lookAt(0, 0.4, 0);

    var group = new THREE.Group();
    scene.add(group);

    var lineMaterial = new THREE.LineBasicMaterial({
      color: 0x5b8def,
      transparent: true,
      opacity: 0.55,
    });
    var boxGeometry = new THREE.BoxGeometry(1, 1, 1);

    var blocks = [];
    for (var x = -2; x <= 2; x++) {
      for (var z = -2; z <= 2; z++) {
        var h = 0.6 + Math.random() * 2.6;
        var edges = new THREE.EdgesGeometry(boxGeometry);
        var line = new THREE.LineSegments(edges, lineMaterial);
        line.position.set(x * 1.15, h / 2, z * 1.15);
        line.scale.set(0.62, h, 0.62);
        group.add(line);
        blocks.push({ line: line, base: h / 2, phase: Math.random() * Math.PI * 2 });
      }
    }

    var pointer = { x: 0, y: 0 };
    function onPointerMove(e) {
      pointer.x = (e.clientX / window.innerWidth - 0.5) * 0.5;
      pointer.y = (e.clientY / window.innerHeight - 0.5) * 0.3;
    }
    window.addEventListener("pointermove", onPointerMove, { passive: true });

    function onResize() {
      width = parent.clientWidth;
      height = parent.clientHeight;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    }
    window.addEventListener("resize", onResize);

    var running = true;
    var rafId = 0;
    var clock = new THREE.Clock();

    function animate() {
      rafId = requestAnimationFrame(animate);
      if (!running) return;
      var t = clock.getElapsedTime();
      group.rotation.y = t * 0.12;
      for (var i = 0; i < blocks.length; i++) {
        var b = blocks[i];
        b.line.position.y = b.base + Math.sin(t * 0.8 + b.phase) * 0.05;
      }
      camera.position.x += (pointer.x - camera.position.x) * 0.04;
      camera.position.y += (2.2 + pointer.y - camera.position.y) * 0.04;
      camera.lookAt(0, 0.4, 0);
      renderer.render(scene, camera);
    }
    animate();

    function onVisibility() {
      running = !document.hidden;
      if (running) clock.start();
    }
    document.addEventListener("visibilitychange", onVisibility);

    function dispose() {
      cancelAnimationFrame(rafId);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("resize", onResize);
      document.removeEventListener("visibilitychange", onVisibility);
      blocks.forEach(function (b) {
        b.line.geometry.dispose();
      });
      boxGeometry.dispose();
      lineMaterial.dispose();
      renderer.dispose();
    }
    window.addEventListener("pagehide", dispose, { once: true });
  }

  ready(function () {
    initSidebar();
    initPageTransitions();
    initReveal();
    initWidgets();
    initAuthHero();
  });

  // Expose a small chart helper used by dashboard pages.
  window.HMS = {
    palette: {
      primary: "#2563eb",
      success: "#10b981",
      warning: "#f59e0b",
      danger: "#ef4444",
      info: "#0ea5e9",
      muted: "#94a3b8",
    },
    currencySymbol:
      (document.querySelector('meta[name="currency-symbol"]') || {}).content || "",
    formatMoney: function (value) {
      var n = Number(value || 0);
      return (
        window.HMS.currencySymbol +
        n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
      );
    },
  };
})();
