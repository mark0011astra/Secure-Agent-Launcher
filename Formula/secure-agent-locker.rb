class SecureAgentLocker < Formula
  include Language::Python::Virtualenv

  desc "Safety-first launcher for AI agent CLIs on macOS"
  homepage "https://github.com/mark0011astra/Secure-Agent-Launcher"
  url "https://github.com/mark0011astra/Secure-Agent-Launcher/archive/refs/heads/main.tar.gz"
  version "main"
  sha256 :no_check
  license "MIT"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    output = shell_output("#{bin}/secure-agent-locker --help")
    assert_match "Safety-first launcher", output
  end
end
