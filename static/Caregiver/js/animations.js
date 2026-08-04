/**
 * GetMeCare Ontario — animations.js
 */
document.addEventListener("DOMContentLoaded", function () {
  /* ═══════════════════════════════════════════════════════
     1. NAVBAR — shadow on scroll
  ═══════════════════════════════════════════════════════ */
  const navbar = document.querySelector(".navbar");
  if (navbar) {
    window.addEventListener(
      "scroll",
      () => {
        navbar.classList.toggle("navbar--scrolled", window.scrollY > 40);
      },
      { passive: true },
    );
  }

  /* ═══════════════════════════════════════════════════════
     2. HERO ENTRANCE (index.html) — stagger in on load
  ═══════════════════════════════════════════════════════ */
  const heroContent = document.querySelector(".hero-content");
  if (heroContent) {
    const items = heroContent.querySelectorAll(
      ".hero-breadcrumb, h1, .hero-sub, .hero-badges, .hero-cta",
    );
    items.forEach((el, i) => {
      el.style.opacity = "0";
      el.style.transform = "translateY(24px)";
      el.style.transition = `opacity 0.7s cubic-bezier(0.22,1,0.36,1) ${i * 120}ms,
                              transform 0.7s cubic-bezier(0.22,1,0.36,1) ${i * 120}ms`;
      requestAnimationFrame(() =>
        requestAnimationFrame(() => {
          el.style.opacity = "1";
          el.style.transform = "translateY(0)";
        }),
      );
    });
  }

  /* ═══════════════════════════════════════════════════════
     3. PAGE-HERO ENTRANCE (terms, privacy, how-it-works, browse, services)
        Elements use .reveal class — fire immediately on load
  ═══════════════════════════════════════════════════════ */
  const pageHero = document.querySelector(
    ".page-hero, .browse-hero, .svc-hero, .contact-hero",
  );
  if (pageHero) {
    const heroRevealEls = pageHero.querySelectorAll(".reveal");
    heroRevealEls.forEach((el, i) => {
      // Already has transition-delay from .reveal-d* classes
      // but override with index-based stagger for the hero
      const base = i * 110;
      el.style.transitionDelay = `${base}ms`;
      // Double rAF ensures styles are applied before transition starts
      requestAnimationFrame(() =>
        requestAnimationFrame(() => {
          el.classList.add("revealed");
        }),
      );
    });

    // Particles inside page-hero / svc-hero
    for (let i = 0; i < 10; i++) {
      const dot = document.createElement("span");
      dot.className = "hero-particle";
      const size = Math.random() * 5 + 2;
      dot.style.cssText = `
        width:${size}px; height:${size}px;
        left:${Math.random() * 100}%;
        top:${Math.random() * 100}%;
        animation-delay:${Math.random() * 4}s;
        animation-duration:${Math.random() * 6 + 5}s;
        opacity:${Math.random() * 0.2 + 0.04};
      `;
      pageHero.appendChild(dot);
    }
  }

  /* ═══════════════════════════════════════════════════════
     4. BROWSE HERO — search bar slide in from right
  ═══════════════════════════════════════════════════════ */
  const browseSearch = document.querySelector(".browse-hero-search");
  if (browseSearch) {
    browseSearch.style.opacity = "0";
    browseSearch.style.transform = "translateX(28px)";
    browseSearch.style.transition =
      "opacity 0.75s cubic-bezier(0.22,1,0.36,1) 0.35s, transform 0.75s cubic-bezier(0.22,1,0.36,1) 0.35s";
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        browseSearch.style.opacity = "1";
        browseSearch.style.transform = "translateX(0)";
      }),
    );
  }

  /* ═══════════════════════════════════════════════════════
     5. SCROLL REVEAL — all .reveal* elements below the fold
  ═══════════════════════════════════════════════════════ */
  const revealEls = document.querySelectorAll(
    ".reveal, .reveal-left, .reveal-right, .reveal-scale",
  );
  // Skip hero elements already handled above
  const scrollRevealEls = Array.from(revealEls).filter(
    (el) =>
      !el.closest(".page-hero") &&
      !el.closest(".browse-hero") &&
      !el.closest(".svc-hero") &&
      !el.closest(".contact-hero") &&
      !el.closest(".hero-content"),
  );

  if (scrollRevealEls.length) {
    const revealObs = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("revealed");
            revealObs.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1, rootMargin: "0px 0px -40px 0px" },
    );

    scrollRevealEls.forEach((el) => revealObs.observe(el));
  }

  /* ═══════════════════════════════════════════════════════
     6. STAGGERED CHILDREN — care-cards, psw-cards, etc.
  ═══════════════════════════════════════════════════════ */
  const staggerParents = document.querySelectorAll(".stagger-children");
  if (staggerParents.length) {
    const staggerObs = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            Array.from(entry.target.children).forEach((child, i) => {
              child.classList.add("reveal");
              child.style.transitionDelay = `${i * 80}ms`;
              requestAnimationFrame(() =>
                requestAnimationFrame(() => {
                  child.classList.add("revealed");
                }),
              );
            });
            staggerObs.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.08 },
    );
    staggerParents.forEach((p) => staggerObs.observe(p));
  }

  /* ═══════════════════════════════════════════════════════
     6b. ANIMATE-ON-SCROLL cards — fade up individually
  ═══════════════════════════════════════════════════════ */
  const scrollCards = document.querySelectorAll(".animate-on-scroll");
  if (scrollCards.length) {
    // Prime styles before observer fires
    scrollCards.forEach((card) => {
      card.style.opacity = "0";
      card.style.transform = "translateY(32px)";
      card.style.transition =
        "opacity 0.6s cubic-bezier(0.22,1,0.36,1), transform 0.6s cubic-bezier(0.22,1,0.36,1)";
    });

    const cardObs = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            // Stagger siblings that are also entering view together
            const siblings = Array.from(
              entry.target.parentElement.querySelectorAll(".animate-on-scroll"),
            );
            const idx = siblings.indexOf(entry.target);
            entry.target.style.transitionDelay = `${idx * 80}ms`;
            entry.target.style.opacity = "1";
            entry.target.style.transform = "translateY(0)";
            cardObs.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.08, rootMargin: "0px 0px -32px 0px" },
    );

    scrollCards.forEach((card) => cardObs.observe(card));
  }

  /* ═══════════════════════════════════════════════════════
     7. STAT COUNTER
  ═══════════════════════════════════════════════════════ */
  const statNums = document.querySelectorAll(".stat-number[data-target]");
  let counted = false;
  const statsBar = document.getElementById("stats-bar");

  if (statsBar && statNums.length) {
    function easeOutQuart(t) {
      return 1 - Math.pow(1 - t, 4);
    }
    function runCounter(el) {
      const target = parseFloat(el.dataset.target);
      const prefix = el.dataset.prefix || "";
      const isFloat = el.dataset.target.includes(".");
      const decs = isFloat ? (el.dataset.target.split(".")[1] || "").length : 0;
      const dur = 1800,
        start = performance.now();
      (function tick(now) {
        const p = Math.min((now - start) / dur, 1);
        const v = easeOutQuart(p) * target;
        el.textContent = prefix + (isFloat ? v.toFixed(decs) : Math.floor(v));
        if (p < 1) requestAnimationFrame(tick);
        else
          el.textContent = prefix + (isFloat ? target.toFixed(decs) : target);
      })(performance.now());
    }
    new IntersectionObserver(
      (entries, obs) => {
        entries.forEach((e) => {
          if (e.isIntersecting && !counted) {
            counted = true;
            statNums.forEach(runCounter);
            obs.disconnect();
          }
        });
      },
      { threshold: 0.3 },
    ).observe(statsBar);
  }

  /* ═══════════════════════════════════════════════════════
     8. HERO TYPEWRITER (index only)
  ═══════════════════════════════════════════════════════ */
  const highlight = document.querySelector(".hero-highlight");
  if (highlight) {
    const words = ["Ontario", "Families", "Seniors", "Ontario"];
    let wi = 0,
      ci = 0,
      deleting = false;
    const speed = { type: 90, delete: 50, pause: 2200 };
    function type() {
      const word = words[wi];
      if (!deleting) {
        highlight.textContent = word.slice(0, ++ci);
        if (ci === word.length) {
          deleting = true;
          setTimeout(type, speed.pause);
          return;
        }
      } else {
        highlight.textContent = word.slice(0, --ci);
        if (ci === 0) {
          deleting = false;
          wi = (wi + 1) % words.length;
        }
      }
      setTimeout(type, deleting ? speed.delete : speed.type);
    }
    setTimeout(type, 1400);
  }

  /* ═══════════════════════════════════════════════════════
     9. HERO PARTICLES (index.html main hero)
  ═══════════════════════════════════════════════════════ */
  const mainHero = document.querySelector(".hero");
  if (mainHero) {
    for (let i = 0; i < 12; i++) {
      const dot = document.createElement("span");
      dot.className = "hero-particle";
      const s = Math.random() * 6 + 3;
      dot.style.cssText = `width:${s}px;height:${s}px;left:${Math.random() * 100}%;top:${Math.random() * 100}%;animation-delay:${Math.random() * 4}s;animation-duration:${Math.random() * 6 + 5}s;opacity:${Math.random() * 0.22 + 0.05};`;
      mainHero.appendChild(dot);
    }
  }

  /* ═══════════════════════════════════════════════════════
     10. CARD TILT — subtle 3D on hover
  ═══════════════════════════════════════════════════════ */
  document
    .querySelectorAll(
      ".psw-card, .care-card, .testimonial-card, .bc-card, .svc-card, .contact-info-card, .contact-response-card, .contact-faq-card",
    )
    .forEach((card) => {
      card.addEventListener("mousemove", (e) => {
        const r = card.getBoundingClientRect();
        const x = ((e.clientX - r.left) / r.width - 0.5) * 7;
        const y = ((e.clientY - r.top) / r.height - 0.5) * -7;
        card.style.transform = `perspective(700px) rotateY(${x}deg) rotateX(${y}deg) translateY(-3px)`;
      });
      card.addEventListener("mouseenter", () => {
        card.style.transition = "transform 0.1s ease";
      });
      card.addEventListener("mouseleave", () => {
        card.style.transition = "transform 0.4s ease";
        card.style.transform = "";
      });
    });

  /* ═══════════════════════════════════════════════════════
     11. BUTTON RIPPLE
  ═══════════════════════════════════════════════════════ */
  document
    .querySelectorAll(
      ".btn-teal, .btn-find-caregiver, .btn-request, .btn-cta-orange, .bhs-btn, .btn-load-more, .btn-contact",
    )
    .forEach((btn) => {
      btn.addEventListener("click", function (e) {
        const ripple = document.createElement("span");
        const r = this.getBoundingClientRect();
        const size = Math.max(r.width, r.height);
        ripple.className = "btn-ripple";
        ripple.style.cssText = `width:${size}px;height:${size}px;left:${e.clientX - r.left - size / 2}px;top:${e.clientY - r.top - size / 2}px;`;
        this.style.position = "relative";
        this.style.overflow = "hidden";
        this.appendChild(ripple);
        setTimeout(() => ripple.remove(), 600);
      });
    });

  /* ═══════════════════════════════════════════════════════
     12. TOC ACTIVE LINK on scroll (legal pages)
  ═══════════════════════════════════════════════════════ */
  const contentSections = document.querySelectorAll(".content-section[id]");
  const tocLinks = document.querySelectorAll(".toc-list a");
  if (contentSections.length && tocLinks.length) {
    window.addEventListener(
      "scroll",
      () => {
        let current = "";
        contentSections.forEach((s) => {
          if (window.scrollY >= s.offsetTop - 130) current = s.id;
        });
        tocLinks.forEach((a) => {
          a.classList.toggle(
            "active",
            a.getAttribute("href") === "#" + current,
          );
        });
      },
      { passive: true },
    );
  }

  /* ═══════════════════════════════════════════════════════
     13. HIIT STEPS — fade-in as user scrolls (how-it-works)
  ═══════════════════════════════════════════════════════ */
  const hiwSteps = document.querySelectorAll(".hiw-step");
  if (hiwSteps.length) {
    const stepObs = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("visible");
            stepObs.unobserve(e.target);
          }
        });
      },
      { threshold: 0.15 },
    );
    hiwSteps.forEach((s) => stepObs.observe(s));
  }
});
