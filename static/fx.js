/* Vera design layer: page transitions, scroll reveal, button ripple, row stagger, count-up. */
(function(){
  var rm = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

  // fade out before moving to another page of the site
  document.addEventListener('click', function(e){
    var a = e.target.closest && e.target.closest('a[href^="/"]');
    if (!a || a.target || e.metaKey || e.ctrlKey || e.shiftKey || rm) return;
    var u = new URL(a.href);
    if (u.origin !== location.origin || u.pathname === location.pathname) return;
    e.preventDefault(); document.body.classList.add('leaving');
    setTimeout(function(){ location.href = a.href; }, 180);
  });
  addEventListener('pageshow', function(e){ if (e.persisted) document.body.classList.remove('leaving'); });

  // ripple on buttons
  document.addEventListener('pointerdown', function(e){
    var b = e.target.closest && e.target.closest('button,.btn');
    if (!b || b.disabled || rm) return;
    var r = b.getBoundingClientRect(), s = Math.max(r.width, r.height), d = document.createElement('span');
    d.className = 'rip';
    d.style.cssText = 'width:'+s+'px;height:'+s+'px;left:'+(e.clientX-r.left-s/2)+'px;top:'+(e.clientY-r.top-s/2)+'px';
    b.appendChild(d); setTimeout(function(){ d.remove(); }, 600);
  });

  // reveal cards as they scroll into view
  if (!rm && 'IntersectionObserver' in window) {
    var io = new IntersectionObserver(function(es){
      es.forEach(function(x){ if (x.isIntersecting) { x.target.classList.add('in'); io.unobserve(x.target); } });
    }, {threshold: .1});
    document.querySelectorAll('main .card, main section').forEach(function(el, i){
      el.classList.add('reveal'); el.style.transitionDelay = (i % 4) * 70 + 'ms'; io.observe(el);
    });
  }

  // table rows glide in the first time a table fills (not on every 3-second refresh)
  document.querySelectorAll('tbody').forEach(function(tb){
    var prev = 0;
    new MutationObserver(function(){
      var n = tb.children.length;
      if (prev === 0 && n > 0 && !rm) {
        Array.prototype.forEach.call(tb.children, function(tr, i){ tr.style.setProperty('--i', Math.min(i, 14)); });
        tb.classList.add('stagger'); setTimeout(function(){ tb.classList.remove('stagger'); }, 1100);
      }
      prev = n;
    }).observe(tb, {childList: true});
  });

  // number count-up (used by the Arena scores)
  window.countUp = function(el, to, suffix){
    suffix = suffix || '%';
    if (rm) { el.textContent = to + suffix; return; }
    var t0 = performance.now();
    function f(t){ var p = Math.min((t - t0) / 900, 1); el.textContent = Math.round(to * (1 - Math.pow(1 - p, 3))) + suffix; if (p < 1) requestAnimationFrame(f); }
    requestAnimationFrame(f);
  };
})();
