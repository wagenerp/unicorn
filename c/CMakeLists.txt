include_directories(./)
add_library(unicornc
  unicorn/idl.c
)

set_property(TARGET unicornc PROPERTY POSITION_INDEPENDENT_CODE ON)

install(TARGETS 
  unicornc
)

install(
  DIRECTORY unicorn
  DESTINATION include
  FILES_MATCHING PATTERN *.h
)
