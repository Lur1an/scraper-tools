{ pkgs, ... }:
{
  pre-commit.hooks = {
    trim-trailing-whitespace.enable = true;
    nixpkgs-fmt.enable = true;
    ruff.enable = true;
    ruff-format.enable = true;
    mypy = {
      enable = true;
      args = [
        "--enable-incomplete-feature=NewGenericSyntax"
      ];
    };
    check-toml.enable = true;
  };

  languages.python = {
    enable = true;
    package = pkgs.python312;
    uv = {
      enable = true;
      sync.enable = true;
    };
  };

  enterShell = ''
    . .devenv/state/venv/bin/activate
  '';
}
