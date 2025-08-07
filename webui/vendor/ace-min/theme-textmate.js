define("ace/theme/textmate",["require","exports","module","ace/theme/textmate-css","ace/lib/dom"],function(e,t,n){"use strict";t.isDark=!1,t.cssClass="ace-tm",t.cssText=e("./textmate-css"),t.$id="ace/theme/textmate";var r=e("../lib/dom");r.importCssString(t.cssText,t.cssClass,!1)});                (function() {
                    window.require(["ace/theme/textmate"], function(m) {
                        if (typeof module == "object" && typeof exports == "object" && module) {
                            module.exports = m;
                        }
                    });
                })();
            