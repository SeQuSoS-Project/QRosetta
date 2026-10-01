// Reads an OpenQASM 2.0 circuit over h, x, rz and cx on stdin, applies Quartz's greedy
// rewriting with the ECC set in argv[1], and writes the result to stdout with angles as
// exact rational multiples of pi.
#include "quartz/tasograph/tasograph.h"

#include <iostream>
#include <iterator>
#include <sstream>

using namespace quartz;

int main(int argc, char **argv) {
  if (argc != 2) {
    std::cerr << "usage: quartz-greedy <ecc_set.json> < input.qasm" << std::endl;
    return 2;
  }
  std::string qasm((std::istreambuf_iterator<char>(std::cin)),
                   std::istreambuf_iterator<char>());
  ParamInfo param_info;
  Context ctx({GateType::input_qubit, GateType::input_param, GateType::cx,
               GateType::h, GateType::rz, GateType::x, GateType::add},
              &param_info);
  EquivalenceSet eqs;
  if (!eqs.load_json(&ctx, argv[1], /*from_verifier=*/false)) {
    std::cerr << "cannot load the ECC set " << argv[1] << std::endl;
    return 3;
  }
  auto graph = Graph::from_qasm_str(&ctx, qasm);
  if (!graph) {
    std::cerr << "Quartz could not parse the circuit" << std::endl;
    return 4;
  }
  auto optimized = graph->greedy_optimize(&ctx, eqs, /*print_message=*/false);
  std::cout << optimized->to_qasm(false, false);
  return 0;
}
