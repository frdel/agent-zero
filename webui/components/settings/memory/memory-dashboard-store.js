import { createStore } from "/js/AlpineStore.js";
import { getContext } from "/index.js";
import * as API from "/js/api.js";

const model = {
  memories: [],
  loading: true,
  error: null,

  // Filter states
  areaFilter: "",
  searchQuery: "",
  currentPage: 1,
  itemsPerPage: 10,

  // Statistics
  totalCount: 0,
  knowledgeCount: 0,
  conversationCount: 0,
  areasCount: {},

  // UI state
  selectedMemory: null,
  showDetailModal: false,
  message: null, // For displaying initialization messages

  async initialize() {
    await this.loadMemories();
  },

  async loadMemories() {
    this.loading = true;
    this.error = null;
    this.message = null;

    try {
      const response = await API.callJsonApi("memory_dashboard", {
        context: getContext(),
        area: this.areaFilter,
        search: this.searchQuery,
        limit: 500 // Get more for client-side pagination
      });

      if (response.success) {
        this.memories = response.memories || []; // Already sorted by API
        this.totalCount = response.total_count || 0;
        this.knowledgeCount = response.knowledge_count || 0;
        this.conversationCount = response.conversation_count || 0;
        this.areasCount = response.areas_count || {};
        this.message = response.message || null; // Handle initialization messages
        this.currentPage = 1; // Reset to first page when loading new data
      } else {
        this.error = response.error || "Failed to load memories";
        this.memories = [];
        this.message = null;
      }
    } catch (error) {
      this.error = error.message || "Failed to load memories";
      this.memories = [];
      this.message = null;
      console.error("Memory dashboard error:", error);
    } finally {
      this.loading = false;
    }
  },

  async applyFilters() {
    await this.loadMemories();
  },

  clearFilters() {
    this.areaFilter = "";
    this.searchQuery = "";
    this.applyFilters();
  },

  // Pagination
  get totalPages() {
    return Math.ceil(this.memories.length / this.itemsPerPage);
  },

  get paginatedMemories() {
    const startIndex = (this.currentPage - 1) * this.itemsPerPage;
    const endIndex = startIndex + this.itemsPerPage;
    return this.memories.slice(startIndex, endIndex);
  },

  goToPage(page) {
    if (page >= 1 && page <= this.totalPages) {
      this.currentPage = page;
    }
  },

  nextPage() {
    if (this.currentPage < this.totalPages) {
      this.currentPage++;
    }
  },

  prevPage() {
    if (this.currentPage > 1) {
      this.currentPage--;
    }
  },

  // Memory details
  showMemoryDetails(memory) {
    this.selectedMemory = memory;
    this.showDetailModal = true;
  },

  closeDetailModal() {
    this.showDetailModal = false;
    this.selectedMemory = null;
  },



  // Utility methods
    formatTimestamp(timestamp, compact = false) {
    if (!timestamp || timestamp === "unknown") return "Unknown";
    try {
      // Parse timestamp - assume UTC if no timezone specified
      let date;
      if (timestamp.includes('T') || timestamp.includes('Z') || timestamp.includes('+')) {
        // ISO format with timezone info
        date = new Date(timestamp);
      } else {
        // Assume UTC for plain format "YYYY-MM-DD HH:MM:SS"
        date = new Date(timestamp + ' UTC');
      }

      // Convert to local time and format
      if (compact) {
        // Compact format for table view
        return date.toLocaleString(undefined, {
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          hour12: false
        });
      } else {
        // Full format for detail view
        return date.toLocaleString(undefined, {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false
        });
      }
    } catch {
      return timestamp;
    }
  },

  formatTags(tags) {
    if (!Array.isArray(tags) || tags.length === 0) return "";
    return tags.join(", ");
  },

    getAreaColor(area) {
    if (!area) return '#757575'; // Default color for undefined/null area

    const colors = {
      'main': '#2196F3',
      'fragments': '#4CAF50',
      'solutions': '#FF9800',
      'instruments': '#9C27B0'
    };
    return colors[area.toLowerCase()] || '#757575';
  },

  copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
      // Could show a toast notification here
      console.log("Copied to clipboard");
    }).catch(err => {
      console.error("Failed to copy: ", err);
    });
  },

  async deleteMemory(memory) {
    // Confirm deletion
    const confirmMessage = `Are you sure you want to delete this memory?\n\nArea: ${memory.area}\nContent: ${memory.content_preview}`;
    if (!confirm(confirmMessage)) {
      return;
    }

    try {
      const response = await API.callJsonApi("memory_delete", {
        context: getContext(),
        memory_id: memory.id
      });

      if (response.success) {
        // Close detail modal if the deleted memory is currently shown
        if (this.selectedMemory && this.selectedMemory.id === memory.id) {
          this.closeDetailModal();
        }

        // Remove memory from local array
        this.memories = this.memories.filter(m => m.id !== memory.id);
        this.totalCount = this.memories.length;

        // Update statistics
        if (memory.knowledge_source) {
          this.knowledgeCount = Math.max(0, this.knowledgeCount - 1);
        } else {
          this.conversationCount = Math.max(0, this.conversationCount - 1);
        }

        // Update areas count
        if (this.areasCount[memory.area]) {
          this.areasCount[memory.area] = Math.max(0, this.areasCount[memory.area] - 1);
          if (this.areasCount[memory.area] === 0) {
            delete this.areasCount[memory.area];
          }
        }

        // Adjust current page if needed
        if (this.paginatedMemories.length === 0 && this.currentPage > 1) {
          this.currentPage--;
        }

        console.log("Memory deleted successfully");
      } else {
        alert("Failed to delete memory: " + (response.error || "Unknown error"));
      }
    } catch (error) {
      console.error("Delete memory error:", error);
      alert("Failed to delete memory: " + error.message);
    }
  },

  // Export functionality (optional)
  exportMemories() {
    const dataStr = JSON.stringify(this.memories, null, 2);
    const dataBlob = new Blob([dataStr], {type: 'application/json'});
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `memory-export-${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }
};

const store = createStore("memoryDashboardStore", model);

export { store };
