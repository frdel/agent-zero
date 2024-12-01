# Notes on url

* aha: absolute path and absolute URI are different. the ambiguity
  tripped me up.
* still, absolute() doesn't require host, i don't think
* doctest in child() doesn't have "d", only "c"
* could try moving off urlparse onto urlutils functions
* what would a mutable api look like?
* queryparamsdict has its own independent applications
* no mention of family (ip hosts?)
* percentDecode includes a decode call with utf8 hardcoded
* if a percent-encoded item fails to decode, and stays percent
  encoded, then what happens when you re-encode? It doesn't get
  double-percent encoded because of the safe + '%' on line 71?
* asURI says "decoded", shouldn't it say "encoded"?

and more:

* so a URL does not know if it's an IRI or a URI.
* In the current API there's no way to go from a URI with non-UTF8
  percent encodings to a fully-decoded IRI
* probably shouldn't even bother with path params (even though i think
  it's supported by stdlib by urllib.splitattr and
  urlparse._splitparams and maybe elsewhere)
* is fragment really quotable?
* better to have path as list or path as string
* for username:password with an empty password, does the colon really still
  have to be present? §3.2.1 suggests yes
* Invalid URLs can have invalid IPv6 constants or invalid port strings
  (including on txurl an empty port)
* is userinfo percent encoded or idna encoded?
* interesting how IDNA is only mentioned <5 times in RFC3986
* surprising lack of error handling on .fromText(), given that it's
  the most common dev interface
* per _percentDecode if a string can't be encoded to ascii, then it
  won't be unquoted.


# inno

* path should be a string, because the "rooted" thing is awkward to
  work with. also because slash-separation doesn't apply to URNs and
  other URL use cases.
* userinfo as a string is a bit dangerous. database connection strings
  still use username:password, and the password might need to be
  escaped. expecting the user to join them safely can lead to issues.
* could have a better error message on non-ascii encoded bytestrings
  passed into fromText() (right now it gives a codec error on path
  split)
* with_port to force port to be in the output, even if it's the default
* larger default port map
* the new URL carries with it a more usable API, with the possible
  limitation that you can't create a URL without knowing its
  underlying encoding. While URLs may technically be able to store
  binary data, I did not find any instances of this in the
  wild. Binary data in URLs is usually represented with base64-encoded
  data.
* TODO: what's up with uses_netloc (e.g., urn is not urn://a:b:c, but
  rather urn:a:b:c)
* _url.URL(u'lol0l0lxyz:asdfk@bcd') silently makes a URL obj with a scheme
