// open all shadow doms
(function () {
  const originalAttachShadow = Element.prototype.attachShadow;
  Element.prototype.attachShadow = function attachShadow(options) {
    return originalAttachShadow.call(this, { ...options, mode: "open" });
  };
})();

// // Create a global bridge for iframe communication
// (function() {
//   let elementCounter = 0;
//   const ignoredTags = [
//     "style",
//     "script",
//     "meta",
//     "link",
//     "svg",
//     "noscript",
//     "path",
//   ];

//   function isElementVisible(element) {
//     // Return true for non-element nodes
//     if (element.nodeType !== Node.ELEMENT_NODE) {
//       return true;
//     }

//     const computedStyle = window.getComputedStyle(element);

//     // Check if element is hidden via CSS
//     if (
//       computedStyle.display === "none" ||
//       computedStyle.visibility === "hidden" ||
//       computedStyle.opacity === "0"
//     ) {
//       return false;
//     }

//     // Check for hidden input type
//     if (element.tagName === "INPUT" && element.type === "hidden") {
//       return false;
//     }

//     // Check for hidden attribute
//     if (
//       element.hasAttribute("hidden") ||
//       element.getAttribute("aria-hidden") === "true"
//     ) {
//       return false;
//     }

//     return true;
//   }

//   function convertAttribute(tag, attr) {
//     let out = {
//       name: attr.name,
//       value: attr.value,
//     };

//     if (["srcset"].includes(out.name)) return null;
//     if (out.name.startsWith("data-") && out.name != "data-A0UID" && out.name != "data-a0-frame-id") return null;

//     if (tag === "img" && out.value.startsWith("data:")) out.value = "data...";

//     return out;
//   }

//   // This function will be available in all frames
//   window.__A0_extractFrameContent = function() {
//     // Get the current frame's DOM content
//     const extractContent = (node) => {
//       if (!node) return "";
      
//       let content = "";
//       const tagName = node.tagName ? node.tagName.toLowerCase() : "";
      
//       // Skip ignored tags
//       if (tagName && ignoredTags.includes(tagName)) {
//         return "";
//       }

//       if (node.nodeType === Node.ELEMENT_NODE) {
//         // Add unique ID to the actual DOM element
//         if (tagName) {
//           const uid = elementCounter++;
//           node.setAttribute("data-A0UID", uid);
//         }

//         content += `<${tagName}`;

//         // Add invisible attribute if element is not visible
//         if (!isElementVisible(node)) {
//           content += " invisible";
//         }

//         // Add attributes with conversion
//         for (let attr of node.attributes) {
//           const out = convertAttribute(tagName, attr);
//           if (out) content += ` ${out.name}="${out.value}"`;
//         }

//         if (tagName) {
//           content += ` selector="${node.getAttribute("data-A0UID")}"`;
//         }
        
//         content += ">";
        
//         // Handle shadow DOM
//         if (node.shadowRoot) {
//           content += "<!-- Shadow DOM Start -->";
//           for (let shadowChild of node.shadowRoot.childNodes) {
//             content += extractContent(shadowChild);
//           }
//           content += "<!-- Shadow DOM End -->";
//         }
        
//         // Handle child nodes
//         for (let child of node.childNodes) {
//           content += extractContent(child);
//         }
        
//         content += `</${tagName}>`;
//       } else if (node.nodeType === Node.TEXT_NODE) {
//         content += node.textContent;
//       } else if (node.nodeType === Node.COMMENT_NODE) {
//         content += `<!--${node.textContent}-->`;
//       }
      
//       return content;
//     };

//     return extractContent(document.documentElement);
//   };

//   // Setup message listener in each frame
//   window.addEventListener('message', function(event) {
//     if (event.data === 'A0_REQUEST_CONTENT') {
//       // Extract content and send it back to parent
//       const content = window.__A0_extractFrameContent();
//       // Use '*' as targetOrigin since we're in a controlled environment
//       window.parent.postMessage({
//         type: 'A0_FRAME_CONTENT',
//         content: content,
//         frameId: window.frameElement?.getAttribute('data-a0-frame-id')
//       }, '*');
//     }
//   });

//   // Function to extract content from all frames
//   window.__A0_extractAllFramesContent = async function(rootNode = document) {
//     let content = "";
    
//     // Extract content from current document
//     content += window.__A0_extractFrameContent();
    
//     // Find all iframes
//     const iframes = rootNode.getElementsByTagName('iframe');
    
//     // Create a map to store frame contents
//     const frameContents = new Map();
    
//     // Setup promise for each iframe
//     const framePromises = Array.from(iframes).map((iframe) => {
//       return new Promise((resolve) => {
//         const frameId = 'frame_' + Math.random().toString(36).substr(2, 9);
//         iframe.setAttribute('data-a0-frame-id', frameId);
        
//         // Setup one-time message listener for this specific frame
//         const listener = function(event) {
//           if (event.data?.type === 'A0_FRAME_CONTENT' && 
//               event.data?.frameId === frameId) {
//             frameContents.set(frameId, event.data.content);
//             window.removeEventListener('message', listener);
//             resolve();
//           }
//         };
//         window.addEventListener('message', listener);
        
//         // Request content from frame
//         iframe.contentWindow.postMessage('A0_REQUEST_CONTENT', '*');
        
//         // Timeout after 2 seconds
//         setTimeout(resolve, 2000);
//       });
//     });
    
//     // Wait for all frames to respond or timeout
//     await Promise.all(framePromises);
    
//     // Add frame contents in order
//     for (let iframe of iframes) {
//       const frameId = iframe.getAttribute('data-a0-frame-id');
//       const frameContent = frameContents.get(frameId);
//       if (frameContent) {
//         content += `<!-- IFrame ${iframe.src || 'unnamed'} Content Start -->`;
//         content += frameContent;
//         content += `<!-- IFrame Content End -->`;
//       }
//     }
    
//     return content;
//   };
// })();

// // override iframe creation to inject our script into them
// (function() {
//   // Store the original createElement to use for iframe creation
//   const originalCreateElement = document.createElement;

//   // Override createElement to catch iframe creation
//   document.createElement = function(tagName, options) {
//     const element = originalCreateElement.call(document, tagName, options);
//     if (tagName.toLowerCase() === 'iframe') {
//       // Override the src setter
//       const originalSrcSetter = Object.getOwnPropertyDescriptor(HTMLIFrameElement.prototype, 'src').set;
//       Object.defineProperty(element, 'src', {
//         set: function(value) {
//           // Call original setter
//           originalSrcSetter.call(this, value);
          
//           // Wait for load and inject our script
//           this.addEventListener('load', () => {
//             try {
//               // Try to inject our script into the iframe
//               const iframeDoc = this.contentWindow.document;
//               const script = iframeDoc.createElement('script');
//               script.textContent = `
//                 // Make iframe accessible
//                 document.domain = document.domain;
//                 // Disable security policies if possible
//                 if (window.SecurityPolicyViolationEvent) {
//                   window.SecurityPolicyViolationEvent = undefined;
//                 }
//               `;
//               iframeDoc.head.appendChild(script);
//             } catch(e) {
//               console.warn('Could not inject into iframe:', e);
//             }
//           }, { once: true });
//         }
//       });
//     }
//     return element;
//   };
// })();