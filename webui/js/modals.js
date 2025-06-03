// Import the component loader and page utilities
import { importComponent } from "/js/components.js";

// Modal functionality
const modalStack = [];

// Create a single backdrop for all modals
const backdrop = document.createElement("div");
backdrop.className = "modal-backdrop";
backdrop.style.display = "none";
backdrop.style.backdropFilter = "blur(5px)";

// Make sure we only close when clicking directly on the backdrop, not its children
backdrop.addEventListener("click", (event) => {
  if (event.target === backdrop) {
    closeModal();
  }
});
document.body.appendChild(backdrop);

// Function to update z-index for all modals and backdrop
function updateModalZIndexes() {
  // Base z-index for modals
  const baseZIndex = 3000;

  // Update z-index for all modals
  modalStack.forEach((modal, index) => {
    // For first modal, z-index is baseZIndex
    // For second modal, z-index is baseZIndex + 20
    // This leaves room for the backdrop between them
    modal.element.style.zIndex = baseZIndex + index * 20;
  });

  // Always show backdrop
  backdrop.style.display = "block";

  if (modalStack.length > 1) {
    // For multiple modals, position backdrop between the top two
    const topModalIndex = modalStack.length - 1;
    const previousModalZIndex = baseZIndex + (topModalIndex - 1) * 20;
    backdrop.style.zIndex = previousModalZIndex + 10;
  } else if (modalStack.length === 1) {
    // For single modal, position backdrop below it
    backdrop.style.zIndex = baseZIndex - 1;
  } else {
    // No modals, hide backdrop
    backdrop.style.display = "none";
  }
}

// Function to create a new modal element
function createModalElement(name) {
  // Create modal element
  const newModal = document.createElement("div");
  newModal.className = "modal";
  newModal.modalName = name; // save name to the object

  // Add click handler to the modal element to close when clicking outside content
  newModal.addEventListener("click", (event) => {
    // Only close if clicking directly on the modal container, not its content
    if (event.target === newModal) {
      closeModal();
    }
  });


  // Create modal structure
  newModal.innerHTML = `
    <div class="modal-inner">
      <div class="modal-header">
        <h2 class="modal-title"></h2>
        <button class="modal-close">&times;</button>
      </div>
      <div class="modal-scroll">
        <div class="modal-bd"></div>
      </div>
    </div>
  `;

  // Setup close button handler for this specific modal
  const close_button = newModal.querySelector(".modal-close");
  close_button.addEventListener("click", () => closeModal());


  // Add modal to DOM
  document.body.appendChild(newModal);

  // Show the modal
  newModal.classList.add("show");

  // Update modal z-indexes
  updateModalZIndexes();

  return {
    element: newModal,
    title: newModal.querySelector(".modal-title"),
    body: newModal.querySelector(".modal-bd"),
    close: close_button,
    styles: [],
    scripts: [],
  };
}

// Function to open modal with content from URL
export function openModal(modalPath) {
  return new Promise((resolve) => {
    try {
      // Create new modal instance
      const modal = createModalElement();

      new MutationObserver(
        (_, o) =>
          !document.contains(modal.element) && (o.disconnect(), resolve())
      ).observe(document.body, { childList: true, subtree: true });

      // Set a loading state
      modal.body.innerHTML = '<div class="loading">Loading...</div>';

      // Already added to stack above

      // Use importComponent to load the modal content
      // This handles all HTML, styles, scripts and nested components
      // Updated path to use the new folder structure with modal.html
      const componentPath = modalPath; // `modals/${modalPath}/modal.html`;

      // Use importComponent which now returns the parsed document
      importComponent(componentPath, modal.body)
        .then((doc) => {
          // Set the title from the document
          modal.title.innerHTML = doc.title || modalPath;
        })
        .catch((error) => {
          console.error("Error loading modal content:", error);
          modal.body.innerHTML = `<div class="error">Failed to load modal content: ${error.message}</div>`;
        });

      // Add modal to stack and show it
      // Add modal to stack
      modalStack.push(modal);
      modal.element.classList.add("show");
      document.body.style.overflow = "hidden";

      // Update modal z-indexes
      updateModalZIndexes();
    } catch (error) {
      console.error("Error loading modal content:", error);
      resolve();
    }
  });
}

// Function to close modal
export function closeModal(modalName = null) {
  if (modalStack.length === 0) return;

  let modalIndex = modalStack.length - 1; // Default to last modal
  let modal;

  if (modalName) {
    // Find the modal with the specified name in the stack
    modalIndex = modalStack.findIndex((modal) => modal.modalName === modalName);
    if (modalIndex === -1) return; // Modal not found in stack

    // Get the modal from stack at the found index
    modal = modalStack[modalIndex];
    // Remove the modal from stack
    modalStack.splice(modalIndex, 1);
  } else {
    // Just remove the last modal
    modal = modalStack.pop();
  }

  // Remove modal-specific styles and scripts immediately
  modal.styles.forEach((styleId) => {
    document.querySelector(`[data-modal-style="${styleId}"]`)?.remove();
  });
  modal.scripts.forEach((scriptId) => {
    document.querySelector(`[data-modal-script="${scriptId}"]`)?.remove();
  });

  // First remove the show class to trigger the transition
  modal.element.classList.remove("show");

  // Remove the modal element from DOM after animation
  modal.element.addEventListener(
    "transitionend",
    () => {
      // Make sure the modal is completely removed from the DOM
      if (modal.element.parentNode) {
        modal.element.parentNode.removeChild(modal.element);
      }
    },
    { once: true }
  );

  // Fallback in case the transition event doesn't fire
  setTimeout(() => {
    if (modal.element.parentNode) {
      modal.element.parentNode.removeChild(modal.element);
    }
  }, 500); // 500ms should be enough for the transition to complete

  // Handle backdrop visibility and body overflow
  if (modalStack.length === 0) {
    // Hide backdrop when no modals are left
    backdrop.style.display = "none";
    document.body.style.overflow = "";
  } else {
    // Update modal z-indexes
    updateModalZIndexes();
  }
}

// Function to scroll to element by ID within the last modal
export function scrollModal(id) {
  if (!id) return;

  // Get the last modal in the stack
  const lastModal = modalStack[modalStack.length - 1].element;
  if (!lastModal) return;

  // Find the modal container and target element
  const modalContainer = lastModal.querySelector(".modal-scroll");
  const targetElement = lastModal.querySelector(`#${id}`);

  if (modalContainer && targetElement) {
    modalContainer.scrollTo({
      top: targetElement.offsetTop - 20, // 20px padding from top
      behavior: "smooth",
    });
  }
}

// Make scrollModal globally available
globalThis.scrollModal = scrollModal;

// Handle modal content loading from clicks
document.addEventListener("click", async (e) => {
  const modalTrigger = e.target.closest("[data-modal-content]");
  if (modalTrigger) {
    e.preventDefault();
    if (
      modalTrigger.hasAttribute("disabled") ||
      modalTrigger.classList.contains("disabled")
    ) {
      return;
    }
    const modalPath = modalTrigger.getAttribute("href");
    await openModal(modalPath);
  }
});

// Close modal on escape key (closes only the top modal)
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && modalStack.length > 0) {
    closeModal();
  }
});

// also export as global function
globalThis.openModal = openModal;
globalThis.closeModal = closeModal;
globalThis.scrollModal = scrollModal;
