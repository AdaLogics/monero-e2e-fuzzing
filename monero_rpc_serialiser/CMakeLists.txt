add_executable(monero_rpc_serialiser serialiser.cpp)

target_include_directories(monero_rpc_serialiser PRIVATE
  ${CMAKE_SOURCE_DIR}/src
  ${CMAKE_SOURCE_DIR}/external
  ${CMAKE_SOURCE_DIR}/contrib/epee/include
)

target_link_libraries(monero_rpc_serialiser PRIVATE
  epee
)
