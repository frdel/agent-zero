{
  inputs = {
    utils.url = "github:numtide/flake-utils";
  };
  outputs = { self, nixpkgs, utils }: utils.lib.eachDefaultSystem (system:
    let
      pkgs = nixpkgs.legacyPackages.${system};
    in
    {
      packages.default = pkgs.hello;
      devShells.default = pkgs.mkShell {
        buildInputs = with pkgs; [
        (python3.withPackages (pkgs: with pkgs; [ pip ]))
        gcc
        ];
        LD_LIBRARY_PATH = "${pkgs.stdenv.cc.cc.lib}/lib";
      };
    }
  );
}
