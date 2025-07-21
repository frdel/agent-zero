import { createStore } from "/js/AlpineStore.js";
import { fetchApi } from "/js/api.js";

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

  async init() {
    await this.initialize();
  },

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
    const isDuplicate = this.attachments.some(
      (existing) =>
        existing.name === newAttachment.name &&
        existing.file &&
        newAttachment.file &&
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
    console.log("Setting up drag and drop handlers...");
    let dragCounter = 0;

    // Prevent default drag behaviors
    ["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
      document.addEventListener(
        eventName,
        (e) => {
          e.preventDefault();
          e.stopPropagation();
        },
        false
      );
    });

    // Handle drag enter
    document.addEventListener(
      "dragenter",
      (e) => {
        console.log("Drag enter detected");
        dragCounter++;
        if (dragCounter === 1) {
          console.log("Showing drag drop overlay");
          this.showDragDropOverlay();
        }
      },
      false
    );

    // Handle drag leave
    document.addEventListener(
      "dragleave",
      (e) => {
        dragCounter--;
        if (dragCounter === 0) {
          this.hideDragDropOverlay();
        }
      },
      false
    );

    // Handle drop
    document.addEventListener(
      "drop",
      (e) => {
        console.log("Drop detected with files:", e.dataTransfer.files.length);
        dragCounter = 0;
        this.hideDragDropOverlay();

        const files = e.dataTransfer.files;
        this.handleFiles(files);
      },
      false
    );
  },

  // Setup paste event handler for clipboard images
  setupPasteHandler() {
    console.log("Setting up paste handler...");
    document.addEventListener("paste", (e) => {
      console.log("Paste event detected, target:", e.target.tagName);

      const items = e.clipboardData.items;
      let imageFound = false;
      console.log("Checking clipboard items:", items.length);

      // First, check if there are any images in the clipboard
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.type.indexOf("image") !== -1) {
          imageFound = true;
          const blob = item.getAsFile();
          if (blob) {
            e.preventDefault(); // Prevent default paste behavior for images
            this.handleClipboardImage(blob);
            console.log("Image detected in clipboard, processing...");
          }
          break; // Only handle the first image found
        }
      }

      // If no images found and we're in an input field, let normal text paste happen
      if (
        !imageFound &&
        (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")
      ) {
        console.log(
          "No images in clipboard, allowing normal text paste in input field"
        );
        return;
      }

      // If no images found and not in input field, do nothing
      if (!imageFound) {
        console.log("No images in clipboard");
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
      const file = new File([blob], filename, { type: "image/png" });

      // Create attachment object
      const attachment = {
        file: file,
        type: "image",
        name: filename,
        extension: "png",
        displayInfo: this.getAttachmentDisplayInfo(file),
      };

      // Read as data URL for preview
      const reader = new FileReader();
      reader.onload = (e) => {
        attachment.url = e.target.result;
        this.addAttachment(attachment);
      };
      reader.readAsDataURL(file);

      // Show success feedback
      console.log("Clipboard image pasted successfully:", filename);
    } catch (error) {
      console.error("Failed to handle clipboard image:", error);
    }
  },

  // Update handleFileUpload to use the attachments store
  handleFileUpload(event) {
    const files = event.target.files;
    this.handleFiles(files);
    event.target.value = ""; // clear uploader selection to fix issue where same file is ignored the second time
  },

  // File handling logic (moved from index.js)
  handleFiles(files) {
    console.log("handleFiles called with", files.length, "files");
    Array.from(files).forEach((file) => {
      console.log("Processing file:", file.name, file.type);
      const ext = file.name.split(".").pop().toLowerCase();
      const isImage = ["jpg", "jpeg", "png", "bmp", "gif", "webp", "svg"].includes(
        ext
      );

      const attachment = {
        file: file,
        type: isImage ? "image" : "file",
        name: file.name,
        extension: ext,
        displayInfo: this.getAttachmentDisplayInfo(file),
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
    return this.attachments.map((attachment) => {
      if (attachment.type === "image") {
        return {
          ...attachment,
          url: URL.createObjectURL(attachment.file),
        };
      } else {
        return {
          ...attachment,
        };
      }
    });
  },

  // Generate server-side API URL for file (for device sync)
  getServerImgUrl(filename) {
    return `/image_get?path=/a0/tmp/uploads/${encodeURIComponent(filename)}`;
  },

  getServerFileUrl(filename) {
    return `/a0/tmp/uploads/${encodeURIComponent(filename)}`;
  },

  // Check if file is an image based on extension
  isImageFile(filename) {
    const imageExtensions = ["jpg", "jpeg", "png", "gif", "bmp", "webp", "svg"];
    const extension = filename.split(".").pop().toLowerCase();
    return imageExtensions.includes(extension);
  },

  // Get attachment preview URL (server URL for persistence, blob URL for current session)
  getAttachmentPreviewUrl(attachment) {
    // If attachment has a name and we're dealing with a server-stored file
    if (typeof attachment === "string") {
      // attachment is just a filename (from loaded chat)
      return this.getServerImgUrl(attachment);
    } else if (attachment.name && attachment.file) {
      // attachment is an object from current session
      if (attachment.type === "image") {
        // For images, use blob URL for current session preview
        return attachment.url || URL.createObjectURL(attachment.file);
      } else {
        // For non-image files, use server URL to get appropriate icon
        return this.getServerImgUrl(attachment.name);
      }
    }
    return null;
  },

  getFilePreviewUrl(filename) {
    const extension = filename.split(".").pop().toLowerCase();
    const types = {
      // Archive files
      zip: "archive",
      rar: "archive",
      "7z": "archive",
      tar: "archive",
      gz: "archive",
      // Document files
      pdf: "document",
      doc: "document",
      docx: "document",
      txt: "document",
      rtf: "document",
      odt: "document",
      // Code files
      py: "code",
      js: "code",
      html: "code",
      css: "code",
      json: "code",
      xml: "code",
      md: "code",
      yml: "code",
      yaml: "code",
      sql: "code",
      sh: "code",
      bat: "code",
      // Spreadsheet files
      xls: "document",
      xlsx: "document",
      csv: "document",
      // Presentation files
      ppt: "document",
      pptx: "document",
      odp: "document",
    };
    const type = types[extension] || "file";
    return `/public/${type}.svg`;
  },

  // Enhanced method to get attachment display info for UI
  getAttachmentDisplayInfo(attachment) {
    if (typeof attachment === "string") {
      // attachment is filename only (from persistent storage)
      const filename = attachment;
      const extension = filename.split(".").pop();
      const isImage = this.isImageFile(filename);
      const previewUrl = isImage
        ? this.getServerImgUrl(filename)
        : this.getFilePreviewUrl(filename);

      return {
        filename: filename,
        extension: extension.toUpperCase(),
        isImage: isImage,
        previewUrl: previewUrl,
        clickHandler: () => {
          if (this.isImageFile(filename)) {
            this.openImageModal(this.getServerImgUrl(filename), filename);
          } else {
            this.downloadAttachment(filename);
          }
        },
      };
    } else {
      // attachment is object (from current session)
      const isImage = this.isImageFile(attachment.name);
      const filename = attachment.name;
      const extension = filename.split(".").pop() || "";
      const previewUrl = isImage
        ? this.getServerImgUrl(attachment.name)
        : this.getFilePreviewUrl(attachment.name);
      return {
        filename: filename,
        extension: extension.toUpperCase(),
        isImage: attachment.type === "image",
        previewUrl: previewUrl,
        clickHandler: () => {
          if (attachment.type === "image") {
            const imageUrl = this.getServerImgUrl(attachment.name);
            this.openImageModal(imageUrl, attachment.name);
          } else {
            this.downloadAttachment(attachment.name);
          }
        },
      };
    }
  },

  async downloadAttachment(filename) {
    try {
      const path = this.getServerFileUrl(filename);
      const response = await fetchApi("/download_work_dir_file?path=" + path);

      if (!response.ok) {
        throw new Error("Network response was not ok");
      }

      const blob = await response.blob();

      const link = document.createElement("a");
      link.href = window.URL.createObjectURL(blob);
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(link.href);
    } catch (error) {
      window.toastFetchError("Error downloading file", error);
      alert("Error downloading file");
    }
  },

  // Generate GUID for unique filenames
  generateGUID() {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(
      /[xy]/g,
      function (c) {
        const r = (Math.random() * 16) | 0;
        const v = c == "x" ? r : (r & 0x3) | 0x8;
        return v.toString(16);
      }
    );
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
      window.openModal("chat/attachments/imageModal.html");
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
    const img = document.querySelector(".modal-image");
    if (img) {
      img.style.transform = `scale(${this.zoomLevel})`;
    }
  },
};

const store = createStore("chatAttachments", model);

export { store };
