// webui/js/i18n.js
i18next
  .use(i18nextHttpBackend)
  // .use(i18nextBrowserLanguageDetector) // Removed
  .init({
    lng: 'zh', // Set default language to Chinese
    fallbackLng: 'en', // Fallback language
    debug: true, // Set to false in production
    ns: ['translation'], // Default namespace
    defaultNS: 'translation',
    backend: {
      loadPath: 'locales/{{lng}}.json', // Path to translation files
    },
    // detection: { ... } // Removed
  }, (err, t) => {
    if (err) return console.error('Error initializing i18next:', err);
    console.log('i18next initialized.');
    // Initial translation of static elements after i18next is ready
    // updateContent is called by the 'initialized' event instead.
  });

// Function to update content
function updateContent() {
  console.log('Updating content based on selected language:', i18next.language);

  // Update textContent for elements with data-i18n
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    const translation = i18next.t(key);
    // Only update if translation exists and is different, to avoid unnecessary changes
    if (translation !== key && el.textContent !== translation) {
      el.textContent = translation;
    } else if (translation === key) {
      // console.warn(`Translation not found for key: ${key}`);
    }
  });

  // Update placeholder for elements with data-i18n-placeholder
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.dataset.i18nPlaceholder;
    const translation = i18next.t(key);
    if (translation !== key && el.placeholder !== translation) {
      el.placeholder = translation;
    } else if (translation === key) {
      // console.warn(`Placeholder translation not found for key: ${key}`);
    }
  });

  // Update title for elements with data-i18n-title
  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    const key = el.dataset.i18nTitle;
    const translation = i18next.t(key);
    if (translation !== key && el.title !== translation) {
      el.title = translation;
    } else if (translation === key) {
      // console.warn(`Title translation not found for key: ${key}`);
    }
  });

  // Update aria-label for elements with data-i18n-aria-label (optional, if you decide to use this pattern)
  document.querySelectorAll('[data-i18n-aria-label]').forEach(el => {
    const key = el.dataset.i18nArialabel; // Note: dataset property names are camelCased
    const translation = i18next.t(key);
    if (translation !== key && el.getAttribute('aria-label') !== translation) {
      el.setAttribute('aria-label', translation);
    } else if (translation === key) {
      // console.warn(`Aria-label translation not found for key: ${key}`);
    }
  });

  // Update html lang attribute
  const currentLang = i18next.language;
  if (document.documentElement.lang !== currentLang) {
    document.documentElement.lang = currentLang;
  }

  // Update Alpine.js components that rely on translated text, if necessary
  // This might involve dispatching a custom event that Alpine components can listen to,
  // or directly calling methods on components if they are accessible.
  // For example, if an Alpine component needs to re-initialize its text:
  // window.dispatchEvent(new CustomEvent('language-changed-event'));
  // Then in your Alpine component: window.addEventListener('language-changed-event', () => { this.text = i18next.t('myKey'); });

  // For x-text attributes that use dynamic keys like the pause/resume button:
  // We need to ensure Alpine reacts to language changes.
  // A simple way is to make i18next reactive within Alpine's context or trigger updates.
  // If $store.i18n.t() is used in x-text, and $store.i18n is an Alpine store
  // wrapping i18next, changes to language should ideally trigger reactivity.
  // If not, a manual re-evaluation might be needed, or ensure `i18next.language` is part of reactive state.
  if (window.Alpine && window.Alpine.store && window.Alpine.store('i18n')) {
    window.Alpine.store('i18n').language = currentLang; // Force Alpine to acknowledge the change
  }

}

// Call this function when i18next is ready and when language changes
i18next.on('initialized', (options) => {
  console.log('i18next initialized event triggered.');
  updateContent();
});
i18next.on('languageChanged', (lng) => {
  console.log('i18next languageChanged event triggered to:', lng);
  updateContent();
});

// Make i18next instance available globally for other scripts if needed (optional)
// and as an Alpine.js store for reactivity in x-text attributes
window.i18n = i18next;

if (window.Alpine) {
  window.Alpine.store('i18n', {
    t(key, options) {
      return i18next.t(key, options);
    },
    get language() {
      return i18next.language;
    },
    // Dummy setter to make language reactive, updateContent will actually refresh.
    set language(lng) {
        // This is mainly to make Alpine reactive.
        // The actual language change is handled by i18next.on('languageChanged', updateContent);
    }
  });
}
