import { createStore } from "/js/AlpineStore.js";

const model = {
  // State properties
  attachments: [],
  hasAttachments: false,
  dragDropOverlayVisible: false,

  // Initialize the store
  async initialize() {
    // Setup event listeners for drag and drop
    this.setupDragDropHandlers();
    // Setup paste event listener for clipboard images
    this.setupPasteHandler();
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
      dragCounter++;
      if (dragCounter === 1) {
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
      dragCounter = 0;
      this.hideDragDropOverlay();
      
      const files = e.dataTransfer.files;
      this.handleFiles(files);
    }, false);
  },

  // Setup paste event handler for clipboard images
  setupPasteHandler() {
    document.addEventListener('paste', (e) => {
      const items = e.clipboardData.items;
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.type.indexOf('image') !== -1) {
          const blob = item.getAsFile();
          this.handleClipboardImage(blob);
        }
      }
    });
  },

  // Handle clipboard image pasting
  async handleClipboardImage(blob) {
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
  },

  // File handling logic (moved from index.js)
  handleFiles(files) {
    Array.from(files).forEach(file => {
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
  }
};

const store = createStore("chatAttachments", model);

export { store }; 