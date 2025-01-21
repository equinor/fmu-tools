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
    echo "Installing test dependencies..."
    pip install ".[tests]"
}

copy_test_files () {
    echo "Copy test files to test folder $CI_TEST_ROOT..."
    cp -r $CI_SOURCE_ROOT/tests $CI_TEST_ROOT/tests
    # Pytest configuration is in pyproject.toml
    cp $CI_SOURCE_ROOT/pyproject.toml $CI_TEST_ROOT
}

start_tests () {
    echo "Running fmu-tools tests with pytest..."
    pytest
}