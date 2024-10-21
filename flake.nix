{
  description = "argo-wrapper";

  inputs =
    {
      nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
      systems.url = "github:nix-systems/default";
      devenv.url = "github:cachix/devenv";
      devenv.inputs.nixpkgs.follows = "nixpkgs";
      poetry2nix.url = "github:nix-community/poetry2nix";
      pre-commit-hooks.url = "github:cachix/pre-commit-hooks.nix";
    };

  nixConfig = {
    extra-trusted-public-keys = "devenv.cachix.org-1:w1cLUi8dv3hnoSPGAuibQv+f9TZLr6cv/Hm9XgU50cw=";
    extra-substituters = "https://devenv.cachix.org";
  };

  outputs = { self, nixpkgs, systems, ... } @ inputs:
    let
      forEachSystem = nixpkgs.lib.genAttrs (import systems);
      pkgsFor = forEachSystem (system: (nixpkgs.legacyPackages.${system}));
    in
    {
      checks = forEachSystem (
        system:
        {
          pre-commit-check = inputs.pre-commit-hooks.lib.${system}.run {
            src = ./.;
            hooks = {
              trim-trailing-whitespace.enable = true;
            };
          };
        }
        // self.packages.${system}
      );
      packages = forEachSystem (system:
        let
          pkgs = pkgsFor.${system};
          inherit (inputs.poetry2nix.lib.mkPoetry2Nix { inherit pkgs; }) mkPoetryApplication defaultPoetryOverrides;
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

      devShells = forEachSystem (system:
        let
          pkgs = pkgsFor.${system};
          inherit (inputs.poetry2nix.lib.mkPoetry2Nix { inherit pkgs; }) mkPoetryEnv defaultPoetryOverrides;
        in
        {
          default = inputs.devenv.lib.mkShell {
            inherit inputs pkgs;
            modules = [
              ({ pkgs
               , config
               , ...
               }: {
                enterShell = self.checks.${system}.pre-commit-check.shellHook;
                packages = with nixpkgs.legacyPackages.${system}; [
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
              })
            ];
          };
        });
    };
}
