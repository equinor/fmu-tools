# This shell script is to be sourced and run from a github workflow
# when fmu-tools is to be tested towards a new RMS enviroment

run_tests () {
    copy_test_files

    install_test_dependencies

    pushd $CI_TEST_ROOT
    start_tests
    popd
}

install_test_dependencies () {
    pip install ".[dev]"
}

copy_test_files () {
    cp -r $CI_SOURCE_ROOT/tests $CI_TEST_ROOT/tests
    # Pytest configuration is in pyproject.toml
    cp $CI_SOURCE_ROOT/pyproject.toml $CI_TEST_ROOT
}

start_tests () {
    pytest
}