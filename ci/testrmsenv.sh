# This shell script is to be sourced and run from a github workflow
# when fmu-tools is to be tested towards a new RMS Python enviroment

run_tests () {
    set_test_variables

    copy_test_files

    install_test_dependencies

    run_pytest
}

set_test_variables() {
    echo "Setting variables for xtgeo tests..."
    CI_TEST_ROOT=$CI_ROOT/fmutools-test-root
}

copy_test_files () {
    echo "Copy xtgeo testdata for xtgeo related tests..."
    if ! [ -d $XTGEO_TESTDATA_PATH ]; then
        echo "Cloning xtgeo-testdata to $XTGEO_TESTDATA_PATH..."
        git clone --depth=1 https://github.com/equinor/xtgeo-testdata $XTGEO_TESTDATA_PATH
    else
        echo "xtgeo testdata already exists at path $XTGEO_TESTDATA_PATH. Skipping copy."
    fi

    echo "Copy fmu-tools test files to test folder $CI_TEST_ROOT..."
    mkdir -p $CI_TEST_ROOT  
    cp -r $PROJECT_ROOT/tests $CI_TEST_ROOT/tests
    cp $PROJECT_ROOT/pyproject.toml $CI_TEST_ROOT
}

install_test_dependencies () {
    echo "Installing test dependencies..."
    pip install ".[tests]"

    echo "Dependencies installed successfully. Listing installed dependencies..."
    pip list
}

run_pytest () {
    echo "Running fmu-tools tests with pytest..."
    pushd $CI_TEST_ROOT
    pytest -n 4 -vv -m "not skipunlessroxar"
    popd
}