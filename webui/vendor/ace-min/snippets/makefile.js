define("ace/snippets/makefile.snippets",["require","exports","module"],function(e,t,n){n.exports="snippet ifeq\n	ifeq (${1:cond0},${2:cond1})\n		${3:code}\n	endif\n"}),define("ace/snippets/makefile",["require","exports","module","ace/snippets/makefile.snippets"],function(e,t,n){"use strict";t.snippetText=e("./makefile.snippets"),t.scope="makefile"});                (function() {
                    window.require(["ace/snippets/makefile"], function(m) {
                        if (typeof module == "object" && typeof exports == "object" && module) {
                            module.exports = m;
                        }
                    });
                })();
            