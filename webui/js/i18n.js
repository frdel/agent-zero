// webui/js/i18n.js
console.log('i18n.js: Script start');

// Function to update content (defined earlier to be available)
function updateContent() {
  console.log('i18n.js: updateContent() called. Current i18next.language:', i18next.language);
  console.log('i18n.js: updateContent() - Translating "testKey":', i18next.t('testKey'));
  // Attempt to log i18next.options; fallback if stringify fails
  try {
    console.log('i18n.js: updateContent() - i18next.options:', JSON.stringify(i18next.options));
  } catch (e) {
    console.log('i18n.js: updateContent() - i18next.options (raw):', i18next.options);
  }

  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    const translation = i18next.t(key);
    // console.log('i18n.js: updateContent() - Element [data-i18n]:', el, 'Key:', key, 'Translation:', translation); // Verbose, remove if too noisy
    if (translation !== key && el.textContent !== translation) {
      el.textContent = translation;
    } else if (translation === key && el.textContent !== key && !(el.textContent.startsWith('[zh]') && el.textContent.substring(5) === key)) {
      // console.warn('i18n.js: updateContent() - TextContent translation not found (or key is value) for key:', key, 'Current text:', el.textContent);
    }
  });

  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const key = el.dataset.i18nPlaceholder;
    const translation = i18next.t(key);
    // console.log('i18n.js: updateContent() - Element [data-i18n-placeholder]:', el, 'Key:', key, 'Translation:', translation); // Verbose
    if (translation !== key && el.placeholder !== translation) {
      el.placeholder = translation;
    } else if (translation === key && el.placeholder !== key && !(el.placeholder.startsWith('[zh]') && el.placeholder.substring(5) === key)) {
      // console.warn('i18n.js: updateContent() - Placeholder translation not found (or key is value) for key:', key, 'Current placeholder:', el.placeholder);
    }
  });

  document.querySelectorAll('[data-i18n-title]').forEach(el => {
    const key = el.dataset.i18nTitle;
    const translation = i18next.t(key);
    // console.log('i18n.js: updateContent() - Element [data-i18n-title]:', el, 'Key:', key, 'Translation:', translation); // Verbose
    if (translation !== key && el.title !== translation) {
      el.title = translation;
    } else if (translation === key && el.title !== key && !(el.title.startsWith('[zh]') && el.title.substring(5) === key)) {
      // console.warn('i18n.js: updateContent() - Title translation not found (or key is value) for key:', key, 'Current title:', el.title);
    }
  });

  document.querySelectorAll('[data-i18n-aria-label]').forEach(el => {
    const key = el.dataset.i18nArialabel;
    const translation = i18next.t(key);
    // console.log('i18n.js: updateContent() - Element [data-i18n-aria-label]:', el, 'Key:', key, 'Translation:', translation); // Verbose
    const currentAriaLabel = el.getAttribute('aria-label');
    if (translation !== key && currentAriaLabel !== translation) {
      el.setAttribute('aria-label', translation);
    } else if (translation === key && currentAriaLabel !== key && !(currentAriaLabel && currentAriaLabel.startsWith('[zh]') && currentAriaLabel.substring(5) === key)) {
      // console.warn('i18n.js: updateContent() - Aria-label translation not found (or key is value) for key:', key, 'Current aria-label:', currentAriaLabel);
    }
  });

  const currentLang = i18next.language;
  if (document.documentElement.lang !== currentLang) {
    document.documentElement.lang = currentLang;
  }

  if (window.Alpine && window.Alpine.store && window.Alpine.store('i18n')) {
    window.Alpine.store('i18n').language = currentLang;
  }
  console.log('i18n.js: updateContent() finished.');
}

console.log('i18n.js: Initializing i18next with explicit initial lng preference:', 'zh');
i18next
  .use(i18nextHttpBackend)
  .use(i18nextBrowserLanguageDetector)
  .init({
    lng: 'zh', // Explicitly set Chinese as the desired initial language
    fallbackLng: 'en',
    debug: true,
    ns: ['translation'],
    defaultNS: 'translation',
    backend: {
      loadPath: 'locales/{{lng}}.json',
    },
    detection: {
      order: ['querystring', 'localStorage', 'cookie'], // Simplified order
      lookupQuerystring: 'lng',
      lookupCookie: 'i18next',
      lookupLocalStorage: 'i18nextLng',
      caches: ['localStorage', 'cookie'],
      excludeCacheFor: ['cimode'],
    }
  }, (err, t_init) => {
    // This callback fires AFTER detection has run and an initial language is set.
    console.log('i18n.js: i18next.init base callback. Detected/Initial language:', i18next.language);
    console.log('i18n.js: i18next.init base callback. Attempting to translate "testKey":', t_init('testKey'));
    if (err) {
        console.error('i18n.js: Error during i18next.init base:', err);
    }

    if (i18next.language !== 'zh') {
        console.log(`i18n.js: Initial language is ${i18next.language}. Forcing change to 'zh'.`);
        i18next.changeLanguage('zh', (err_change, t_change) => {
            if (err_change) {
                console.error('i18n.js: Error changing language to zh:', err_change);
            } else {
                console.log('i18n.js: Language successfully changed to zh. Translating "testKey":', t_change('testKey'));
            }
            console.log('i18n.js: Resources for zh/translation after potential changeLanguage:', JSON.stringify(i18next.getResourceBundle('zh', 'translation')));
            console.log('i18n.js: Resources for en/translation after potential changeLanguage:', JSON.stringify(i18next.getResourceBundle('en', 'translation')));
            updateContent(); // Update content after attempting to change to 'zh'
        });
    } else {
        console.log("i18n.js: Initial language already 'zh'. Proceeding to update content.");
        console.log('i18n.js: Resources for zh/translation (already zh):', JSON.stringify(i18next.getResourceBundle('zh', 'translation')));
        console.log('i18n.js: Resources for en/translation (already zh):', JSON.stringify(i18next.getResourceBundle('en', 'translation')));
        updateContent();
    }
  });

// This event is for subsequent language changes AFTER initial setup.
i18next.on('languageChanged', (lng) => {
  console.log('i18n.js: i18next languageChanged event. New language:', lng);
  console.log('i18n.js: i18next languageChanged event. Attempting to translate "testKey":', i18next.t('testKey'));
  updateContent();
});

i18next.on('initialized', (options) => {
  console.log('i18n.js: i18next initialized event. Current language:', i18next.language);
  // The main content update is now handled more directly in the init callback to ensure 'zh' priority.
  // This event listener can still be useful for other post-initialization tasks if needed.
  // console.log('i18n.js: i18next initialized event. Attempting to translate "testKey":', i18next.t('testKey'));
  // console.log('i18n.js: i18next initialized event. Loaded languages:', i18next.languages);
  // updateContent(); // This call might be redundant if the init callback logic always calls updateContent.
});

window.i18n = i18next;

if (window.Alpine) {
  window.Alpine.store('i18n', {
    t(key, options) {
      return i18next.t(key, options);
    },
    get language() {
      return i18next.language;
    },
    set language(lng) {
      // Reactive dummy setter
    }
  });
}
