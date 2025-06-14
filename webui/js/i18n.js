// webui/js/i18n.js
const translations = {};
let currentLanguage = 'en'; // Default language

async function loadTranslations(lang) {
    try {
        const response = await fetch(`locales/${lang}.json`);
        if (!response.ok) {
            console.error(`Could not load ${lang}.json: ${response.statusText}`);
            // Fallback to English if the language file is not found
            if (lang !== 'en') {
                await loadTranslations('en');
            }
            return;
        }
        const data = await response.json();
        translations[lang] = data;
        currentLanguage = lang;
            localStorage.setItem('preferredLanguage', lang);
            document.documentElement.lang = lang;
        console.log(`${lang.toUpperCase()} translations loaded.`);
            document.dispatchEvent(new CustomEvent('languageChanged', { detail: { language: lang } }));
    } catch (error) {
        console.error(`Error loading translations for ${lang}:`, error);
        // Fallback to English on any error
        if (lang !== 'en') {
            await loadTranslations('en');
        }
    }
}

function setLanguage(lang) {
    if (translations[lang]) {
        currentLanguage = lang;
        localStorage.setItem('preferredLanguage', lang);
        document.documentElement.lang = lang; // Set the lang attribute on the HTML element
        translatePage();
            document.dispatchEvent(new CustomEvent('languageChanged', { detail: { language: lang } }));
    } else {
        loadTranslations(lang).then(() => {
            if (translations[lang]) {
                // currentLanguage, localStorage, and documentElement.lang are set by loadTranslations
                // Event dispatch is also handled within loadTranslations on success
                translatePage(); // Just need to translate the page
            } else {
                console.warn(`Translations for ${lang} not available after attempting to load.`);
            }
        });
    }
}

function __(key, ...args) {
    let langToUse = currentLanguage;
    if (!translations[langToUse]) {
        // If current language translations are not loaded, try 'en'
        langToUse = 'en';
    }
    if (!translations[langToUse]) {
        // If 'en' is also not loaded, return the key as fallback
        console.warn(`No translations loaded for ${currentLanguage} or en. Key: ${key}`);
        return key;
    }

    let text = translations[langToUse][key] || translations['en']?.[key] || key;

    if (args.length > 0) {
        args.forEach((arg, index) => {
            const placeholder = new RegExp(`\{${index}\}`, 'g');
            text = text.replace(placeholder, arg);
        });
    }
    return text;
}

function translatePage() {
    document.querySelectorAll('[data-i18n-key]').forEach(element => {
        const key = element.getAttribute('data-i18n-key');
        const isHtml = element.hasAttribute('data-i18n-html');
        const translation = __(key);

        if (isHtml) {
            element.innerHTML = translation;
        } else {
            // Handle different ways text is set (textContent, value, placeholder)
            if (element.nodeName === 'INPUT' || element.nodeName === 'TEXTAREA') {
                if (element.hasAttribute('placeholder')) {
                    element.placeholder = translation;
                } else {
                    element.value = translation;
                }
            } else {
                element.textContent = translation;
            }
        }
    });
    // Special handling for title
    const titleElement = document.querySelector('title');
    if (titleElement) {
        const key = titleElement.getAttribute('data-i18n-key');
        if (key) {
            titleElement.textContent = __(key);
        }
    }
}

// Function to get the current language
function getCurrentLanguage() {
    return currentLanguage;
}

// Expose functions to global window object (or use ES6 modules if preferred)
window.i18n = {
    loadTranslations,
    setLanguage,
    translate: __,
    translatePage,
    getCurrentLanguage
};

// Load English by default
// await loadTranslations('en'); // This will be called from index.js
