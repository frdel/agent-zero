define("ace/snippets/maze.snippets",["require","exports","module"],function(e,t,n){n.exports="snippet >\ndescription assignment\nscope maze\n	-> ${1}= ${2}\n\nsnippet >\ndescription if\nscope maze\n	-> IF ${2:**} THEN %${3:L} ELSE %${4:R}\n"}),define("ace/snippets/maze",["require","exports","module","ace/snippets/maze.snippets"],function(e,t,n){"use strict";t.snippetText=e("./maze.snippets"),t.scope="maze"});                (function() {
                    window.require(["ace/snippets/maze"], function(m) {
                        if (typeof module == "object" && typeof exports == "object" && module) {
                            module.exports = m;
                        }
                    });
                })();
            