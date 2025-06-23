console.log('attachmentsStore.js module loading...');
import { createStore } from "/js/AlpineStore.js";

console.log('attachmentsStore.js module loaded, creating model...');
const model = {
  // State properties
  attachments: [],
  hasAttachments: false,
  dragDropOverlayVisible: false,

  // Image modal properties
  currentImageUrl: null,
  currentImageName: null,
  imageLoaded: false,
  imageError: false,
  zoomLevel: 1,

  // Initialize the store
  async initialize() {
    console.log('Initializing attachments store...');
    // Setup event listeners for drag and drop
    this.setupDragDropHandlers();
    // Setup paste event listener for clipboard images
    this.setupPasteHandler();
    console.log('Attachments store initialized successfully');
  },

  // Basic attachment management methods
  addAttachment(attachment) {
    // Validate for duplicates
    if (this.validateDuplicates(attachment)) {
      this.attachments.push(attachment);
      this.updateAttachmentState();
    }
  },

  removeAttachment(index) {
    if (index >= 0 && index < this.attachments.length) {
      this.attachments.splice(index, 1);
      this.updateAttachmentState();
    }
  },

  clearAttachments() {
    this.attachments = [];
    this.updateAttachmentState();
  },

  validateDuplicates(newAttachment) {
    // Check if attachment already exists based on name and size
    const isDuplicate = this.attachments.some(existing => 
      existing.name === newAttachment.name && 
      existing.file && newAttachment.file &&
      existing.file.size === newAttachment.file.size
    );
    return !isDuplicate;
  },

  updateAttachmentState() {
    this.hasAttachments = this.attachments.length > 0;
  },

  // Drag drop overlay control methods
  showDragDropOverlay() {
    this.dragDropOverlayVisible = true;
  },

  hideDragDropOverlay() {
    this.dragDropOverlayVisible = false;
  },

  // Setup drag and drop event handlers
  setupDragDropHandlers() {
    console.log('Setting up drag and drop handlers...');
    let dragCounter = 0;

    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      document.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
      }, false);
    });

    // Handle drag enter
    document.addEventListener('dragenter', (e) => {
      console.log('Drag enter detected');
      dragCounter++;
      if (dragCounter === 1) {
        console.log('Showing drag drop overlay');
        this.showDragDropOverlay();
      }
    }, false);

    // Handle drag leave
    document.addEventListener('dragleave', (e) => {
      dragCounter--;
      if (dragCounter === 0) {
        this.hideDragDropOverlay();
      }
    }, false);

    // Handle drop
    document.addEventListener('drop', (e) => {
      console.log('Drop detected with files:', e.dataTransfer.files.length);
      dragCounter = 0;
      this.hideDragDropOverlay();
      
      const files = e.dataTransfer.files;
      this.handleFiles(files);
    }, false);
  },

  // Setup paste event handler for clipboard images
  setupPasteHandler() {
    console.log('Setting up paste handler...');
    document.addEventListener('paste', (e) => {
      console.log('Paste event detected, target:', e.target.tagName);
      
      const items = e.clipboardData.items;
      let imageFound = false;
      console.log('Checking clipboard items:', items.length);
      
      // First, check if there are any images in the clipboard
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.type.indexOf('image') !== -1) {
          imageFound = true;
          const blob = item.getAsFile();
          if (blob) {
            e.preventDefault(); // Prevent default paste behavior for images
            this.handleClipboardImage(blob);
            console.log('Image detected in clipboard, processing...');
          }
          break; // Only handle the first image found
        }
      }

      // If no images found and we're in an input field, let normal text paste happen
      if (!imageFound && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) {
        console.log('No images in clipboard, allowing normal text paste in input field');
        return;
      }

      // If no images found and not in input field, do nothing
      if (!imageFound) {
        console.log('No images in clipboard');
      }
    });
  },

  // Handle clipboard image pasting
  async handleClipboardImage(blob) {
    try {
      // Generate unique filename
      const guid = this.generateGUID();
      const filename = `clipboard-${guid}.png`;
      
      // Create file object from blob
      const file = new File([blob], filename, { type: 'image/png' });
      
      // Create attachment object
      const attachment = {
        file: file,
        type: 'image',
        name: filename,
        extension: 'png'
      };

      // Read as data URL for preview
      const reader = new FileReader();
      reader.onload = (e) => {
        attachment.url = e.target.result;
        this.addAttachment(attachment);
      };
      reader.readAsDataURL(file);

      // Show success feedback
      console.log('Clipboard image pasted successfully:', filename);
      
    } catch (error) {
      console.error('Failed to handle clipboard image:', error);
    }
  },

  // File handling logic (moved from index.js)
  handleFiles(files) {
    console.log('handleFiles called with', files.length, 'files');
    Array.from(files).forEach(file => {
      console.log('Processing file:', file.name, file.type);
      const ext = file.name.split('.').pop().toLowerCase();
      const isImage = ['jpg', 'jpeg', 'png', 'bmp', 'gif', 'webp'].includes(ext);

      const attachment = {
        file: file,
        type: isImage ? 'image' : 'file',
        name: file.name,
        extension: ext
      };

      if (isImage) {
        // Read image as data URL for preview
        const reader = new FileReader();
        reader.onload = (e) => {
          attachment.url = e.target.result;
          this.addAttachment(attachment);
        };
        reader.readAsDataURL(file);
      } else {
        // For non-image files, add directly
        this.addAttachment(attachment);
      }
    });
  },

  // Get attachments for sending message
  getAttachmentsForSending() {
    return this.attachments.map(attachment => {
      if (attachment.type === 'image') {
        return {
          ...attachment,
          url: URL.createObjectURL(attachment.file)
        };
      } else {
        return {
          ...attachment
        };
      }
    });
  },

  // Generate GUID for unique filenames
  generateGUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c == 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  },

  // Image modal methods
  openImageModal(imageUrl, imageName) {
    this.currentImageUrl = imageUrl;
    this.currentImageName = imageName;
    this.imageLoaded = false;
    this.imageError = false;
    this.zoomLevel = 1;
    
    // Open the modal using the modals system
    if (window.openModal) {
      window.openModal('chat/attachments/imageModal.html');
    }
  },

  closeImageModal() {
    this.currentImageUrl = null;
    this.currentImageName = null;
    this.imageLoaded = false;
    this.imageError = false;
    this.zoomLevel = 1;
  },

  // Zoom controls
  zoomIn() {
    this.zoomLevel = Math.min(this.zoomLevel * 1.2, 5); // Max 5x zoom
    this.updateImageZoom();
  },

  zoomOut() {
    this.zoomLevel = Math.max(this.zoomLevel / 1.2, 0.1); // Min 0.1x zoom
    this.updateImageZoom();
  },

  resetZoom() {
    this.zoomLevel = 1;
    this.updateImageZoom();
  },

  updateImageZoom() {
    const img = document.querySelector('.modal-image');
    if (img) {
      img.style.transform = `scale(${this.zoomLevel})`;
    }
  }
};

console.log('Creating chatAttachments store...');
const store = createStore("chatAttachments", model);
console.log('chatAttachments store created:', store);

export { store }; 