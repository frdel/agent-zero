define("ace/snippets/fsl.snippets",["require","exports","module"],function(e,t,n){n.exports='snippet header\n	machine_name     : "";\n	machine_author   : "";\n	machine_license  : MIT;\n	machine_comment  : "";\n	machine_language : en;\n	machine_version  : 1.0.0;\n	fsl_version      : 1.0.0;\n	start_states     : [];\n'}),define("ace/snippets/fsl",["require","exports","module","ace/snippets/fsl.snippets"],function(e,t,n){"use strict";t.snippetText=e("./fsl.snippets"),t.scope="fsl"});                (function() {
                    window.require(["ace/snippets/fsl"], function(m) {
                        if (typeof module == "object" && typeof exports == "object" && module) {
                            module.exports = m;
                        }
                    });
                })();
            