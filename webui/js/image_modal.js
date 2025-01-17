// Singleton interval ID for image refresh
let activeIntervalId = null;

export async function openImageModal(src, refreshInterval = 0) {
  try {
    let imgSrc = src;
    
    // Clear any existing refresh interval
    if (activeIntervalId !== null) {
      clearInterval(activeIntervalId);
      activeIntervalId = null;
    }
    
    if (refreshInterval > 0) {
      // Add or update timestamp to bypass cache
      const addTimestamp = (url) => {
        const urlObj = new URL(url, window.location.origin);
        urlObj.searchParams.set('t', Date.now());
        return urlObj.toString();
      };

      // Check if image viewer is still active
      const isImageViewerActive = () => {
        const container = document.querySelector('#image-viewer-container');
        if (!container) return false;
        
        // Check if element or any parent is hidden
        let element = container;
        while (element) {
          const style = window.getComputedStyle(element);
          if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
            return false;
          }
          element = element.parentElement;
        }
        return true;
      };

      // Preload next image before displaying
      const preloadAndUpdate = async (currentImg) => {
        const nextSrc = addTimestamp(src);
        // Create a promise that resolves when the image is loaded
        const preloadPromise = new Promise((resolve, reject) => {
          const tempImg = new Image();
          tempImg.onload = () => resolve(nextSrc);
          tempImg.onerror = reject;
          tempImg.src = nextSrc;
        });
        
        try {
          // Wait for preload to complete
          const loadedSrc = await preloadPromise;
          // Check if this interval is still the active one
          if (currentImg && isImageViewerActive()) {
            currentImg.src = loadedSrc;
          }
        } catch (err) {
          console.error('Failed to preload image:', err);
        }
      };
      
      imgSrc = addTimestamp(src);
      
      // Set up periodic refresh with preloading
      activeIntervalId = setInterval(() => {
        if (!isImageViewerActive()) {
          clearInterval(activeIntervalId);
          activeIntervalId = null;
          return;
        }
        const img = document.querySelector('.image-viewer-img');
        if (img) {
          preloadAndUpdate(img);
        }
      }, refreshInterval);
    }

    const html = `<div id="image-viewer-container"><img class="image-viewer-img" src="${imgSrc}" /></div>`;
    const fileName = src.split("/").pop();
    
    // Open the modal with the generated HTML
    await window.genericModalProxy.openModal(fileName, "", html);
  } catch (e) {
    window.toastFetchError("Error fetching history", e);
    return;
  }
}
