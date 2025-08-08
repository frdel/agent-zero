define("ace/snippets/haml.snippets",["require","exports","module"],function(e,t,n){n.exports="snippet t\n	%table\n		%tr\n			%th\n				${1:headers}\n		%tr\n			%td\n				${2:headers}\nsnippet ul\n	%ul\n		%li\n			${1:item}\n		%li\nsnippet =rp\n	= render :partial => '${1:partial}'\nsnippet =rpl\n	= render :partial => '${1:partial}', :locals => {}\nsnippet =rpc\n	= render :partial => '${1:partial}', :collection => @$1\n\n"}),define("ace/snippets/haml",["require","exports","module","ace/snippets/haml.snippets"],function(e,t,n){"use strict";t.snippetText=e("./haml.snippets"),t.scope="haml"});                (function() {
                    window.require(["ace/snippets/haml"], function(m) {
                        if (typeof module == "object" && typeof exports == "object" && module) {
                            module.exports = m;
                        }
                    });
                })();
            