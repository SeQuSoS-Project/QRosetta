// Generates the Nam gate-set (h, x, rz, cx) ECC set: 3 qubits, 2 symbolic parameters,
// circuits of up to argv[1] gates, written to <argv[2]>complete_ECC_set.json.
#include "test/gen_ecc_set.h"

#include <cstdlib>

using namespace quartz;

int main(int argc, char **argv) {
  if (argc != 3) {
    std::cerr << "usage: gen-nam-ecc <max_gates> <file_prefix>" << std::endl;
    return 2;
  }
  gen_ecc_set({GateType::rz, GateType::h, GateType::cx, GateType::x, GateType::add},
              argv[2], /*unique_parameters=*/true, /*generate_representative_set=*/false,
              /*num_qubits=*/3, /*num_input_parameters=*/2, std::atoi(argv[1]));
  return 0;
}
