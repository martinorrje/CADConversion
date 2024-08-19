{
  description = "CAD Conversion development environment";

  inputs = {
    nixpkgs.url = "nixpkgs/nixos-24.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, flake-utils, nixpkgs, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        fhs = pkgs.buildFHSUserEnv {
          name = "cad-conversion-dev";
          targetPkgs = _: [ pkgs.micromamba ];
          runScript = "bash";
        };
      in { devShells.default = fhs.env; });
}
