// iBU home page interactions: theme toggle, mobile menu, seal marquee, app carousel, cookie banner.
(function () {
    const root = document.documentElement;

    function storageGet(key) {
        try {
            return localStorage.getItem(key);
        } catch (e) {
            return null;
        }
    }

    function storageSet(key, value) {
        try {
            localStorage.setItem(key, value);
        } catch (e) {
            // Storage unavailable (private mode, blocked site data): keep working without persistence.
        }
    }

    // Theme toggle
    const themeToggle = document.querySelector('[data-theme-toggle]');
    function syncThemeToggle() {
        const dark = root.classList.contains('dark');
        themeToggle.setAttribute('aria-checked', String(dark));
        themeToggle.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
    }
    themeToggle.addEventListener('click', () => {
        const dark = !root.classList.contains('dark');
        root.classList.toggle('dark', dark);
        root.style.colorScheme = dark ? 'dark' : 'light';
        storageSet('theme', dark ? 'dark' : 'light');
        syncThemeToggle();
    });
    syncThemeToggle();

    // Mobile navigation
    const menuToggle = document.querySelector('[data-menu-toggle]');
    const mobileNav = document.getElementById('mobile-navigation');
    menuToggle.addEventListener('click', () => {
        const open = mobileNav.hidden;
        mobileNav.hidden = !open;
        menuToggle.setAttribute('aria-expanded', String(open));
        menuToggle.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
    });
    mobileNav.addEventListener('click', (event) => {
        if (event.target.closest('a')) {
            mobileNav.hidden = true;
            menuToggle.setAttribute('aria-expanded', 'false');
        }
    });

    // Seal marquee: duplicate the group so translateX(-50%) loops seamlessly.
    const marqueeTrack = document.querySelector('[data-marquee-track]');
    const sealGroup = marqueeTrack.querySelector('.ibu-seal-group');
    const sealCopy = sealGroup.cloneNode(true);
    sealCopy.setAttribute('aria-hidden', 'true');
    marqueeTrack.appendChild(sealCopy);

    // App screen carousel
    const carousel = document.querySelector('[data-app-carousel]');
    const slides = Array.from(carousel.querySelectorAll('[data-carousel-slide]'));
    const label = carousel.querySelector('[data-carousel-label]');
    const dotsContainer = carousel.querySelector('[data-carousel-dots]');
    let current = 0;
    let autoplay;

    const dots = slides.map((slide, index) => {
        const dot = document.createElement('button');
        dot.type = 'button';
        dot.className = 'ibu-carousel-dot';
        dot.setAttribute('aria-label', 'Show ' + slide.dataset.label);
        dot.addEventListener('click', () => {
            goTo(index);
            restartAutoplay();
        });
        dotsContainer.appendChild(dot);
        return dot;
    });

    function goTo(index) {
        const count = slides.length;
        current = (index + count) % count;
        slides.forEach((slide, i) => {
            let offset = i - current;
            if (offset > count / 2) offset -= count;
            if (offset < -count / 2) offset += count;
            slide.dataset.offset = Math.abs(offset) <= 1 ? String(offset) : 'hidden';
            slide.setAttribute('aria-hidden', String(offset !== 0));
        });
        dots.forEach((dot, i) => dot.setAttribute('aria-current', String(i === current)));
        label.textContent = slides[current].dataset.label;
    }

    function restartAutoplay() {
        clearInterval(autoplay);
        if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            autoplay = setInterval(() => goTo(current + 1), 4500);
        }
    }

    carousel.querySelector('[data-carousel-previous]').addEventListener('click', () => {
        goTo(current - 1);
        restartAutoplay();
    });
    carousel.querySelector('[data-carousel-next]').addEventListener('click', () => {
        goTo(current + 1);
        restartAutoplay();
    });
    carousel.addEventListener('mouseenter', () => clearInterval(autoplay));
    carousel.addEventListener('mouseleave', restartAutoplay);

    goTo(0);
    restartAutoplay();

    // Cookie consent banner
    const banner = document.querySelector('[data-cookie-banner]');
    const details = banner.querySelector('[data-cookie-details]');
    const detailsToggle = banner.querySelector('[data-cookie-toggle]');
    const prefInputs = Array.from(banner.querySelectorAll('[data-cookie-pref]'));

    try {
        const saved = JSON.parse(storageGet('cookie_preferences') || '{}');
        prefInputs.forEach((input) => {
            if (typeof saved[input.dataset.cookiePref] === 'boolean') {
                input.checked = saved[input.dataset.cookiePref];
            }
        });
    } catch (e) {
        // Ignore malformed saved preferences.
    }

    if (storageGet('cookie_consent') !== 'true') {
        banner.hidden = false;
    }

    function savePreferences(acceptAll) {
        const preferences = { essential: true };
        prefInputs.forEach((input) => {
            if (acceptAll) input.checked = true;
            preferences[input.dataset.cookiePref] = input.checked;
        });
        storageSet('cookie_preferences', JSON.stringify(preferences));
        storageSet('cookie_consent', 'true');
        storageSet('cookie_consent_date', new Date().toISOString());
        banner.hidden = true;
    }

    detailsToggle.addEventListener('click', () => {
        const open = details.hidden;
        details.hidden = !open;
        detailsToggle.textContent = open ? 'Hide Details' : 'Customize';
        detailsToggle.setAttribute('aria-expanded', String(open));
    });
    banner.querySelectorAll('[data-cookie-accept-all]').forEach((button) => {
        button.addEventListener('click', () => savePreferences(true));
    });
    banner.querySelector('[data-cookie-accept-selected]').addEventListener('click', () => savePreferences(false));
})();
