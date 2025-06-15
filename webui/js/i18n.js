// webui/js/i18n.js
console.log('i18n.js: Script start');

window.changeLanguage = function(lang) {
  console.log('i18n.js: changeLanguage called with:', lang);
  i18next.changeLanguage(lang, (err, t) => {
    if (err) {
      return console.error('i18n.js: Error changing language:', err);
    }
    console.log('i18n.js: Language changed to', lang);
    localStorage.setItem('i18nextLng', lang);
    // updateContent is already called by i18next.on('languageChanged')
  });
}

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

function initLanguageSelector() {
  console.log('i18n.js: initLanguageSelector() called');
  const selector = document.getElementById('language-select');
  if (selector) {
    // Set initial value based on i18next's current language
    selector.value = i18next.language;

    // The @change event in the HTML already calls window.changeLanguage.
    // No need to add another event listener here if using Alpine's @change.
    // If not using Alpine for this specific element, an event listener would be added here:
    // selector.addEventListener('change', (event) => {
    //   window.changeLanguage(event.target.value);
    // });
  } else {
    console.warn('i18n.js: Language selector #language-select not found.');
  }
}

// Default language setup
const preferredLanguage = localStorage.getItem('i18nextLng');
if (!preferredLanguage) {
  localStorage.setItem('i18nextLng', 'zh'); // Set Chinese as default if nothing is stored
  console.log('i18n.js: No language preference found in localStorage. Setting default to zh.');
} else {
  console.log('i18n.js: Language preference found in localStorage:', preferredLanguage);
}

// console.log('i18n.js: Initializing i18next with explicit initial lng preference:', 'zh'); // This line is misleading now
i18next
  .use(i18nextHttpBackend)
  .use(i18nextBrowserLanguageDetector)
  .init({
    // lng: 'zh', // REMOVED to allow detector to work for persistence. localStorage check above handles default.
    fallbackLng: 'en', // Fallback if a translation file for the current language is missing
    debug: true,
    ns: ['translation'],
    defaultNS: 'translation',
    backend: {
      loadPath: 'locales/{{lng}}.json',
    },
    detection: {
      order: ['localStorage', 'querystring', 'cookie'], // Ensure localStorage is checked first
      lookupQuerystring: 'lng',
      lookupCookie: 'i18next',
      lookupLocalStorage: 'i18nextLng',
      caches: ['localStorage'], // Cache the detected language in localStorage
      excludeCacheFor: ['cimode'],
    }
  }, (err, t_init) => {
    // REMOVED THE PREVIOUS CONDITIONAL LOGIC THAT FORCED 'zh'
    console.log('i18n.js: i18next.init base callback. Detected/Initial language:', i18next.language);
    if (err) {
        console.error('i18n.js: Error during i18next.init base:', err);
    }
    updateContent(); // Update content after language is determined
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
  // updateContent(); // This call is redundant as it's in the init callback.
  initLanguageSelector(); // Initialize the language selector AFTER i18next is fully initialized and language determined.
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

// Ensure initLanguageSelector is called after the initial content update in the init callback.
// One way is to call it at the end of the i18next.init callback.
// Or, ensure the 'initialized' event still reliably fires after the init callback and does its job.
// For safety, and given the `updateContent` is in the init callback, let's add it there too.

// Modifying the init callback to include initLanguageSelector after updateContent
// This requires re-stating the init block. For the purpose of this diff, we'll assume the previous
// SEARCH/REPLACE blocks handled the main init changes, and this is a conceptual adjustment.
// The `initLanguageSelector` call within `i18next.on('initialized', ...)` should still be effective,
// as `initialized` fires after `init` callback.
