from exeg.cli import main

def test_no_args_prints_help_and_fails(capsys):
    assert main([]) == 2
    assert "exeg" in capsys.readouterr().err

def test_version_flag(capsys):
    assert main(["--version"]) == 0
    assert "0.1.0" in capsys.readouterr().out
