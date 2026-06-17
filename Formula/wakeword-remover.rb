class WakewordRemover < Formula
  include Language::Python::Virtualenv

  desc "Deactivate wake words in audio and video files"
  homepage "https://github.com/Visual-Studio-Coder/video-wakeword-remover"
  head "https://github.com/Visual-Studio-Coder/video-wakeword-remover.git", branch: "main"
  license "MIT"

  depends_on "ffmpeg"
  depends_on "python@3.14"

  def install
    virtualenv_create(libexec, "python3.14")
    system libexec/"bin/pip", "install", buildpath
    bin.install_symlink libexec/"bin/wakeword-remover"
  end

  test do
    assert_match "usage:", shell_output("#{bin}/wakeword-remover --help")
  end
end
