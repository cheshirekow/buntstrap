set(buntstrap_py_files
    __init__.py
    __main__.py
    chroot.py
    config.py
    freeze.py
    size_report.py
    util.py)

add_custom_command(OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/buntstrap_format.stamp
                   COMMAND autopep8 -i ${buntstrap_py_files}
                   COMMAND python -Bm cmake_format -i CMakeLists.txt
                           doc/CMakeLists.txt
                   COMMAND touch
                           ${CMAKE_CURRENT_BINARY_DIR}/buntstrap_format.stamp
                   DEPENDS ${buntstrap_py_files}
                   WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
add_custom_target(buntstrap_format
                  DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/buntstrap_format.stamp)
add_dependencies(format buntstrap_format)

add_custom_command(OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/buntstrap_lint.stamp
                   COMMAND pylint ${buntstrap_py_files}
                   COMMAND touch
                           ${CMAKE_CURRENT_BINARY_DIR}/buntstrap_lint.stamp
                   DEPENDS ${buntstrap_py_files}
                   WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})
add_custom_target(buntstrap_lint
                  DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/buntstrap_lint.stamp)

# NOTE(josh): format before lint-check, avoid formatting lint
add_dependencies(buntstrap_lint buntstrap_format)
add_dependencies(lint buntstrap_lint)

add_subdirectory(doc)
