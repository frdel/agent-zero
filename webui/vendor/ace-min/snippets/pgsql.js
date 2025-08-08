;                (function() {
                    window.require(["ace/snippets/pgsql"], function(m) {
                        if (typeof module == "object" && typeof exports == "object" && module) {
                            module.exports = m;
                        }
                    });
                })();
            