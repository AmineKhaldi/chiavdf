import os
import platform
import subprocess
import sys
from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext


class CMakeExtension(Extension):
    def __init__(self, name, sourcedir=""):
        Extension.__init__(self, name, sources=["./"])
        self.sourcedir = os.path.abspath(sourcedir)


class CMakeBuild(build_ext):
    def run(self):
        try:
            subprocess.check_output(["cmake", "--version"])
        except OSError:
            raise RuntimeError(
                "CMake must be installed to build"
                + " the following extensions: "
                + ", ".join(e.name for e in self.extensions)
            )

        for ext in self.extensions:
            self.build_extension(ext)

    def build_extension(self, ext):
        extdir = os.path.abspath(os.path.dirname(self.get_ext_fullpath(ext.name)))
        cmake_args = [
            "-DCMAKE_LIBRARY_OUTPUT_DIRECTORY=" + str(extdir),
            "-DPYTHON_EXECUTABLE=" + sys.executable,
        ]

        cfg = "Debug" if self.debug else "Release"
        build_args = ["--config", cfg]

        if platform.system() == "Windows":
            cmake_args += [
                "-DCMAKE_LIBRARY_OUTPUT_DIRECTORY_{}={}".format(cfg.upper(), extdir)
            ]
        else:
            cmake_args += ["-DCMAKE_BUILD_TYPE=" + cfg]
            build_args += ["--", "-j", "6"]

        env = os.environ.copy()
        env["CXXFLAGS"] = '{} -DVERSION_INFO=\\"{}\\"'.format(
            env.get("CXXFLAGS", ""), self.distribution.get_version()
        )
        if not os.path.exists(self.build_temp):
            os.makedirs(self.build_temp)
        subprocess.check_call(
            ["cmake", ext.sourcedir] + cmake_args, cwd=self.build_temp, env=env
        )
        subprocess.check_call(
            ["cmake", "--build", "."] + build_args, cwd=self.build_temp
        )


class BuildExt(build_ext):
    """A custom build extension for adding compiler-specific options."""

    def build_extensions(self):
        ct = self.compiler.compiler_type
        opts = []
        link_opts = []
        if ct == "unix":
            opts.append('-DVERSION_INFO="%s"' % self.distribution.get_version())
        elif ct == "msvc":
            opts.append('/DVERSION_INFO=\\"%s\\"' % self.distribution.get_version())
        for ext in self.extensions:
            if sys.platform == "darwin":
                darwin_opts = ["-stdlib=libc++", "-mmacosx-version-min=10.14"]
                opts.extend(darwin_opts)
                link_opts.extend(darwin_opts)  # type: ignore
            ext.extra_compile_args = opts
            ext.extra_link_args = link_opts
        build_ext.build_extensions(self)


setup(
    name="chiavdf",
    author="Florin Chirica",
    author_email="florin@chia.net",
    description="Chia vdf verification (wraps C++)",
    license="Apache License",
    python_requires=">=3.7",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/Chia-Network/chiavdf",
    ext_modules=[CMakeExtension("chiavdf", ".")],
    cmdclass=dict(build_ext=CMakeBuild),
    zip_safe=False,
)
