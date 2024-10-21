{
  description = "argo-wrapper";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
  inputs.poetry2nix.url = "github:nix-community/poetry2nix";

  outputs = { self, nixpkgs, poetry2nix }:
    let
      supportedSystems = [ "x86_64-linux" "x86_64-darwin" "aarch64-linux" "aarch64-darwin" ];
      forAllSystems = nixpkgs.lib.genAttrs supportedSystems;
      pkgs = forAllSystems (system: nixpkgs.legacyPackages.${system});
    in
    {
      packages = forAllSystems (system:
        let
          inherit (poetry2nix.lib.mkPoetry2Nix { pkgs = pkgs.${system}; }) mkPoetryApplication defaultPoetryOverrides;
        in
        {
          default = mkPoetryApplication {
            projectDir = self;
            overrides = defaultPoetryOverrides.extend
              (final: prev: {
                cdislogging = prev.cdislogging.overridePythonAttrs
                  (
                    old: {
                      buildInputs = (old.buildInputs or [ ]) ++ [ prev.setuptools ];
                    }
                  );
                cdiserrors = prev.cdiserrors.overridePythonAttrs
                  (old: {
                    buildInputs = (old.buildInputs or [ ]) ++ [
                      prev.poetry-core
                      prev.setuptools
                      prev.wheel
                      prev.pip
                    ];
                    nativeBuildInputs = (old.nativeBuildInputs or [ ]) ++ [
                      prev.poetry
                    ];
                    postPatch = ''
                      ${old.postPatch or ""}
                      sed -i 's/poetry.masonry/poetry.core.masonry/' pyproject.toml
                    '';
                  });
                argo-workflows = prev.argo-workflows.overridePythonAttrs
                  (
                    old: {
                      buildInputs = (old.buildInputs or [ ]) ++ [ prev.setuptools ];
                    }
                  );
                gen3authz = prev.gen3authz.overridePythonAttrs
                  (
                    old: {
                      buildInputs = (old.buildInputs or [ ]) ++ [ prev.setuptools ];
                      nativeBuildInputs = (old.nativeBuildInputs or [ ]) ++ [
                        prev.poetry
                      ];
                      postPatch = ''
                        ${old.postPatch or ""}
                        sed -i 's/poetry.masonry/poetry.core.masonry/' pyproject.toml
                      '';
                    }
                  );
              });
          };
        });

      devShells = forAllSystems (system:
        let
          inherit (poetry2nix.lib.mkPoetry2Nix { pkgs = pkgs.${system}; }) mkPoetryEnv defaultPoetryOverrides;
        in
        {
          default = pkgs.${system}.mkShellNoCC {
            packages = with pkgs.${system}; [
              (mkPoetryEnv {
                projectDir = self;
                overrides = defaultPoetryOverrides.extend
                  (final: prev: {
                    cdislogging = prev.cdislogging.overridePythonAttrs
                      (
                        old: {
                          buildInputs = (old.buildInputs or [ ]) ++ [ prev.setuptools ];
                        }
                      );
                    cdiserrors = prev.cdiserrors.overridePythonAttrs
                      (old: {
                        buildInputs = (old.buildInputs or [ ]) ++ [
                          prev.poetry-core
                          prev.setuptools
                          prev.wheel
                          prev.pip
                        ];
                        nativeBuildInputs = (old.nativeBuildInputs or [ ]) ++ [
                          prev.poetry
                        ];
                        postPatch = ''
                          ${old.postPatch or ""}
                          sed -i 's/poetry.masonry/poetry.core.masonry/' pyproject.toml
                        '';
                      });
                    argo-workflows = prev.argo-workflows.overridePythonAttrs
                      (
                        old: {
                          buildInputs = (old.buildInputs or [ ]) ++ [ prev.setuptools ];
                        }
                      );
                    gen3authz = prev.gen3authz.overridePythonAttrs
                      (
                        old: {
                          buildInputs = (old.buildInputs or [ ]) ++ [ prev.setuptools ];
                          nativeBuildInputs = (old.nativeBuildInputs or [ ]) ++ [
                            prev.poetry
                          ];
                          postPatch = ''
                            ${old.postPatch or ""}
                            sed -i 's/poetry.masonry/poetry.core.masonry/' pyproject.toml
                          '';
                        }
                      );
                  });
              })
              poetry
              postgresql
            ];
            shellHook = ''
              echo "PostgreSQL $(${pkgs.${system}.postgresql}/bin/postgres --version) is available in this shell."
            '';
          };
        });
    };
}
