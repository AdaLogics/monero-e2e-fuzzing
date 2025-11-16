#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <unordered_map>
#include <functional>

#include "storages/portable_storage_template_helper.h"
#include "rpc/core_rpc_server_commands_defs.h"

using namespace cryptonote;

namespace {

// Generic binary serialiser for a given request structure
template <typename T>
epee::byte_slice generate_binary_from_json(const std::string& json_input_text) {
    T request_object;
    if (!epee::serialization::load_t_from_json(request_object, json_input_text)) {
        throw std::runtime_error("Failed to parse JSON input.");
    }
    return epee::serialization::store_t_to_binary(request_object);
}

// Mapping of Monero binary RPC endpoints to their request serialisers
const std::unordered_map<std::string, std::function<epee::byte_slice(const std::string&)>> binary_serialisers = {
    {"/get_blocks.bin",              generate_binary_from_json<COMMAND_RPC_GET_BLOCKS_FAST::request>},
    {"/get_blocks_by_height.bin",    generate_binary_from_json<COMMAND_RPC_GET_BLOCKS_BY_HEIGHT::request>},
    {"/get_hashes.bin",              generate_binary_from_json<COMMAND_RPC_GET_HASHES_FAST::request>},
    {"/get_o_indexes.bin",           generate_binary_from_json<COMMAND_RPC_GET_TX_GLOBAL_OUTPUTS_INDEXES::request>},
    {"/get_outs.bin",                generate_binary_from_json<COMMAND_RPC_GET_OUTPUTS_BIN::request>},
    {"/get_output_distribution.bin", generate_binary_from_json<COMMAND_RPC_GET_OUTPUT_DISTRIBUTION::request>}
};

} // namespace

int main(int argc, char* argv[]) {
    if (argc != 4) {
        std::cerr << "Usage: " << argv[0] << " <input_json_path> <endpoint> <output_bin_path>" << std::endl;
        return 1;
    }

    std::string input_path   = argv[1];
    std::string endpoint     = argv[2];
    std::string output_path  = argv[3];

    // Read JSON input from file
    std::ifstream input_file(input_path);
    if (!input_file) {
        std::cerr << "Failed to open input file: " << input_path << std::endl;
        return 1;
    }
    std::stringstream buffer;
    buffer << input_file.rdbuf();
    std::string json_input_text = buffer.str();

    try {
        const auto& handler = binary_serialisers.find(endpoint);
        if (handler == binary_serialisers.end()) {
            std::cerr << "Unsupported or unknown endpoint: " << endpoint << std::endl;
            return 2;
        }

        // Serialise to binary
        epee::byte_slice binary_output = handler->second(json_input_text);
        std::cerr << "[Debug] Binary output size: " << binary_output.size() << " bytes" << std::endl;

        // Write to output file
        std::ofstream output_file(output_path, std::ios::binary);
        if (!output_file) {
            std::cerr << "Failed to open output file: " << output_path << std::endl;
            return 3;
        }
        output_file.write(reinterpret_cast<const char*>(binary_output.data()), binary_output.size());
        return 0;

    } catch (const std::exception& ex) {
        std::cerr << "Serialisation error: " << ex.what() << std::endl;
        return 4;
    }
}
