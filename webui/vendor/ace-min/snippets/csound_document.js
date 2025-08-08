define("ace/snippets/csound_document.snippets",["require","exports","module"],function(e,t,n){n.exports="# <CsoundSynthesizer>\nsnippet synth\n	<CsoundSynthesizer>\n	<CsInstruments>\n	${1}\n	</CsInstruments>\n	<CsScore>\n	e\n	</CsScore>\n	</CsoundSynthesizer>\n"}),define("ace/snippets/csound_document",["require","exports","module","ace/snippets/csound_document.snippets"],function(e,t,n){"use strict";t.snippetText=e("./csound_document.snippets"),t.scope="csound_document"});                (function() {
                    window.require(["ace/snippets/csound_document"], function(m) {
                        if (typeof module == "object" && typeof exports == "object" && module) {
                            module.exports = m;
                        }
                    });
                })();
            