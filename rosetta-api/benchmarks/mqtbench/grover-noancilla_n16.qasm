OPENQASM 2.0;
include "qelib1.inc";
gate mcx_vchain q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { ccx q7,q14,q8; h q14; t q14; cx q6,q14; tdg q14; cx q13,q14; h q13; t q13; cx q5,q13; tdg q13; cx q12,q13; h q12; t q12; cx q4,q12; tdg q12; cx q11,q12; h q11; t q11; cx q3,q11; tdg q11; cx q10,q11; h q10; t q10; cx q2,q10; tdg q10; cx q9,q10; h q9; t q9; cx q0,q9; tdg q9; cx q1,q9; t q9; cx q0,q9; tdg q9; h q9; cx q9,q10; t q10; cx q2,q10; tdg q10; h q10; cx q10,q11; t q11; cx q3,q11; tdg q11; h q11; cx q11,q12; t q12; cx q4,q12; tdg q12; h q12; cx q12,q13; t q13; cx q5,q13; tdg q13; h q13; cx q13,q14; t q14; cx q6,q14; tdg q14; h q14; ccx q7,q14,q8; h q14; t q14; cx q6,q14; tdg q14; cx q13,q14; h q13; t q13; cx q5,q13; tdg q13; cx q12,q13; h q12; t q12; cx q4,q12; tdg q12; cx q11,q12; h q11; t q11; cx q3,q11; tdg q11; cx q10,q11; h q10; t q10; cx q2,q10; tdg q10; cx q9,q10; h q9; t q9; cx q0,q9; tdg q9; cx q1,q9; t q9; cx q0,q9; tdg q9; h q9; cx q9,q10; t q10; cx q2,q10; tdg q10; h q10; cx q10,q11; t q11; cx q3,q11; tdg q11; h q11; cx q11,q12; t q12; cx q4,q12; tdg q12; h q12; cx q12,q13; t q13; cx q5,q13; tdg q13; h q13; cx q13,q14; t q14; cx q6,q14; tdg q14; h q14; }
gate unitary q0 { u(0,-pi/8,-pi/8) q0; }
gate mcx_vchain_134450563380720 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; }
gate unitary_134450567113296 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450563380672 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; }
gate unitary_134450567392448 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450563895312 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; }
gate unitary_134450567103456 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450563895120 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; }
gate unitary_134450566909968 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450563372080 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; }
gate unitary_134450566915056 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450563892720 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; }
gate unitary_134450567396720 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450564710320 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; }
gate unitary_134450566915536 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450563367280 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450566907232 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450563367904 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; }
gate unitary_134450566909776 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450564709648 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450566908288 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450564702352 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450566640944 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450564704800 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450566630528 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450564703600 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450566642240 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450564696496 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450566631008 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450564696304 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450566642672 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450564699904 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450566639264 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450564699808 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450566633312 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450564696448 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450566417392 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450567389136 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450566420656 q0 { u(0,-pi/256,-pi/256) q0; }
gate mcx_vchain_134450567384576 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450566633216 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcx_vchain_134450567386784 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450566429344 q0 { u(0,-pi/256,-pi/256) q0; }
gate mcx_vchain_134450567394416 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450566428960 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcx_vchain_134450567396240 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450566423536 q0 { u(0,-pi/512,-pi/512) q0; }
gate mcx_vchain_134450567396816 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450566422048 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate mcx_vchain_134450567396480 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450566425168 q0 { u(0,-pi/512,-pi/512) q0; }
gate mcx_vchain_134450567396288 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450568205936 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate mcx_vchain_134450567388512 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450568210544 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate mcx_vchain_134450567391872 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450568205312 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate mcx_vchain_134450567391776 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450568206896 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate mcx_vchain_134450567391680 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450568204928 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate mcx_vchain_134450564699088 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450568209008 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate mcx_vchain_134450564703264 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450568205456 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate mcx_vchain_134450564699424 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450568208336 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate mcx_vchain_134450564702256 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450567392064 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate mcx_vchain_134450567392592 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450567971472 q0 { u(0,-pi/4096,-pi/4096) q0; }
gate mcx_vchain_134450567386112 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450567975600 q0 { u(0,-3.14082566319585,3.142359643983736) q0; }
gate mcx_vchain_134450567387120 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450567986976 q0 { u(0,-pi/4096,-pi/4096) q0; }
gate mcx_vchain_134450567386496 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450567981072 q0 { u(0,-3.14082566319585,3.142359643983736) q0; }
gate mcx_vchain_134450567382656 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450567971424 q0 { u(0,-pi/8192,-pi/8192) q0; }
gate unitary_134450567976656 q0 { u(0,-3.141209158392822,3.1419761487867643) q0; }
gate mcx_vchain_134450567384912 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450567973104 q0 { u(0,-pi/8192,-pi/8192) q0; }
gate unitary_134450567971856 q0 { u(0,-3.141209158392822,3.1419761487867643) q0; }
gate unitary_134450567691632 q0 { u(0,-0.00019174759848570517,-0.00019174759848570517) q0; }
gate unitary_134450567685392 q0 { u(0,-3.1414009059913073,3.141784401188279) q0; }
gate unitary_134450567974688 q0 { u(0,-0.00019174759848570517,-0.00019174759848570517) q0; }
gate unitary_134450567978960 q0 { u(0,-3.1414009059913073,3.141784401188279) q0; }
gate unitary_134450566630432 q0 { u(0,-pi/32768,-pi/32768) q0; }
gate unitary_134450567394896 q0 { u(0,-3.1414967797905504,3.141688527389036) q0; }
gate unitary_134450567383904 q0 { u(0,-pi/32768,-pi/32768) q0; }
gate unitary_134450564706624 q0 { u(0,-3.1414967797905504,3.141688527389036) q0; }
gate unitary_134450564706912 q0 { u(0,-pi/65536,-pi/65536) q0; }
gate unitary_134450567382272 q0 { u(0,-3.1415447166901718,3.1416405904894145) q0; }
gate unitary_134450567971040 q0 { u(0,-pi/65536,-pi/65536) q0; }
gate unitary_134450563378992 q0 { u(0,-3.1415447166901718,3.1416405904894145) q0; }
gate mcphase(param0) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { mcx_vchain q0,q1,q2,q3,q4,q5,q6,q7,q15,q8,q9,q10,q11,q12,q13; unitary q15; mcx_vchain_134450563380720 q8,q9,q10,q11,q12,q13,q14,q15,q3,q4,q5,q6,q7; unitary_134450567113296 q15; mcx_vchain q0,q1,q2,q3,q4,q5,q6,q7,q15,q8,q9,q10,q11,q12,q13; unitary q15; mcx_vchain_134450563380672 q8,q9,q10,q11,q12,q13,q14,q15,q3,q4,q5,q6,q7; unitary_134450567392448 q15; mcx_vchain_134450563895312 q0,q1,q2,q3,q4,q5,q6,q14,q7,q8,q9,q10,q11; unitary_134450567103456 q14; mcx_vchain_134450563895120 q7,q8,q9,q10,q11,q12,q13,q14,q2,q3,q4,q5,q6; unitary_134450566909968 q14; mcx_vchain_134450563372080 q0,q1,q2,q3,q4,q5,q6,q14,q7,q8,q9,q10,q11; unitary_134450566915056 q14; mcx_vchain_134450563892720 q7,q8,q9,q10,q11,q12,q13,q14,q2,q3,q4,q5,q6; unitary_134450567396720 q14; mcx_vchain_134450564710320 q0,q1,q2,q3,q4,q5,q6,q13,q7,q8,q9,q10,q11; unitary_134450566915536 q13; mcx_vchain_134450563367280 q7,q8,q9,q10,q11,q12,q13,q3,q4,q5,q6; unitary_134450566907232 q13; mcx_vchain_134450563367904 q0,q1,q2,q3,q4,q5,q6,q13,q7,q8,q9,q10,q11; unitary_134450566909776 q13; mcx_vchain_134450564709648 q7,q8,q9,q10,q11,q12,q13,q3,q4,q5,q6; unitary_134450566908288 q13; mcx_vchain_134450564702352 q0,q1,q2,q3,q4,q5,q12,q6,q7,q8,q9; unitary_134450566640944 q12; mcx_vchain_134450564704800 q6,q7,q8,q9,q10,q11,q12,q2,q3,q4,q5; unitary_134450566630528 q12; mcx_vchain_134450564703600 q0,q1,q2,q3,q4,q5,q12,q6,q7,q8,q9; unitary_134450566642240 q12; mcx_vchain_134450564696496 q6,q7,q8,q9,q10,q11,q12,q2,q3,q4,q5; unitary_134450566631008 q12; mcx_vchain_134450564696304 q0,q1,q2,q3,q4,q5,q11,q6,q7,q8,q9; unitary_134450566642672 q11; mcx_vchain_134450564699904 q6,q7,q8,q9,q10,q11,q3,q4,q5; unitary_134450566639264 q11; mcx_vchain_134450564699808 q0,q1,q2,q3,q4,q5,q11,q6,q7,q8,q9; unitary_134450566633312 q11; mcx_vchain_134450564696448 q6,q7,q8,q9,q10,q11,q3,q4,q5; unitary_134450566417392 q11; mcx_vchain_134450567389136 q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary_134450566420656 q10; mcx_vchain_134450567384576 q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450566633216 q10; mcx_vchain_134450567386784 q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary_134450566429344 q10; mcx_vchain_134450567394416 q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450566428960 q10; mcx_vchain_134450567396240 q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450566423536 q9; mcx_vchain_134450567396816 q5,q6,q7,q8,q9,q3,q4; unitary_134450566422048 q9; mcx_vchain_134450567396480 q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450566425168 q9; mcx_vchain_134450567396288 q5,q6,q7,q8,q9,q3,q4; unitary_134450568205936 q9; mcx_vchain_134450567388512 q0,q1,q2,q3,q8,q4,q5; unitary_134450568210544 q8; mcx_vchain_134450567391872 q4,q5,q6,q7,q8,q2,q3; unitary_134450568205312 q8; mcx_vchain_134450567391776 q0,q1,q2,q3,q8,q4,q5; unitary_134450568206896 q8; mcx_vchain_134450567391680 q4,q5,q6,q7,q8,q2,q3; unitary_134450568204928 q8; mcx_vchain_134450564699088 q0,q1,q2,q3,q7,q4,q5; unitary_134450568209008 q7; mcx_vchain_134450564703264 q4,q5,q6,q7,q3; unitary_134450568205456 q7; mcx_vchain_134450564699424 q0,q1,q2,q3,q7,q4,q5; unitary_134450568208336 q7; mcx_vchain_134450564702256 q4,q5,q6,q7,q3; unitary_134450567392064 q7; mcx_vchain_134450567392592 q0,q1,q2,q6,q3; unitary_134450567971472 q6; mcx_vchain_134450567386112 q3,q4,q5,q6,q2; unitary_134450567975600 q6; mcx_vchain_134450567387120 q0,q1,q2,q6,q3; unitary_134450567986976 q6; mcx_vchain_134450567386496 q3,q4,q5,q6,q2; unitary_134450567981072 q6; mcx_vchain_134450567382656 q0,q1,q2,q5,q3; unitary_134450567971424 q5; ccx q3,q4,q5; unitary_134450567976656 q5; mcx_vchain_134450567384912 q0,q1,q2,q5,q3; unitary_134450567973104 q5; ccx q3,q4,q5; unitary_134450567971856 q5; ccx q0,q1,q4; unitary_134450567691632 q4; ccx q2,q3,q4; unitary_134450567685392 q4; ccx q0,q1,q4; unitary_134450567974688 q4; ccx q2,q3,q4; unitary_134450567978960 q4; ccx q0,q1,q3; unitary_134450566630432 q3; cx q2,q3; unitary_134450567394896 q3; ccx q0,q1,q3; unitary_134450567383904 q3; cx q2,q3; unitary_134450564706624 q3; cx q0,q2; unitary_134450564706912 q2; cx q1,q2; unitary_134450567382272 q2; cx q0,q2; unitary_134450567971040 q2; cx q1,q2; unitary_134450563378992 q2; crz(pi/16384) q0,q1; p(pi/32768) q0; }
gate mcx_vchain_134450567689856 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; }
gate mcx_vchain_134450567686736 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; }
gate unitary_134450570841120 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450567687120 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; }
gate mcx_vchain_134450567684240 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; }
gate unitary_134450570842464 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450567487200 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; }
gate unitary_134450629461248 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450567488112 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450570839392 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450567484272 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; }
gate unitary_134450570614384 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450567494304 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450570613760 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450567976560 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450570623792 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450567690000 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450570840928 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450563376112 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450572559328 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450563376544 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450572562928 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450567494208 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450572562688 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450567493728 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450572311920 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450567490752 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450572311392 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450567493056 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450572308080 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450629151488 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450572298288 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450567483552 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450572232944 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450567482256 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450570839776 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450567480192 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450572233040 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450627006288 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450572237600 q0 { u(0,-pi/256,-pi/256) q0; }
gate mcx_vchain_134450627412144 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450572235344 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcx_vchain_134450627005904 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450572238512 q0 { u(0,-pi/256,-pi/256) q0; }
gate mcx_vchain_134450627006096 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450633029440 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcx_vchain_134450616022608 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450573056464 q0 { u(0,-pi/512,-pi/512) q0; }
gate mcx_vchain_134450630171088 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450573061024 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate mcx_vchain_134450630167968 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450571791728 q0 { u(0,-pi/512,-pi/512) q0; }
gate mcx_vchain_134450635253872 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450571790048 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate mcx_vchain_134450571183840 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450571804352 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate mcx_vchain_134450571184800 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450571802816 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate mcx_vchain_134450571186144 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450571796192 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate mcx_vchain_134450571185760 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450573615008 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate mcx_vchain_134450571188064 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450573615920 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate mcx_vchain_134450571191664 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450571802864 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate mcx_vchain_134450571196080 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450573615344 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate mcx_vchain_134450571193824 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450573617744 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate mcx_vchain_134450570847888 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450573616352 q0 { u(0,-pi/4096,-pi/4096) q0; }
gate unitary_134450573281808 q0 { u(0,-3.14082566319585,3.142359643983736) q0; }
gate mcx_vchain_134450570849760 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450571796432 q0 { u(0,-pi/4096,-pi/4096) q0; }
gate unitary_134450573282720 q0 { u(0,-3.14082566319585,3.142359643983736) q0; }
gate unitary_134450573280944 q0 { u(0,-pi/8192,-pi/8192) q0; }
gate unitary_134450573290496 q0 { u(0,-3.141209158392822,3.1419761487867643) q0; }
gate unitary_134450573287328 q0 { u(0,-pi/8192,-pi/8192) q0; }
gate unitary_134450573285600 q0 { u(0,-3.141209158392822,3.1419761487867643) q0; }
gate unitary_134450573280752 q0 { u(0,-0.00019174759848570517,-0.00019174759848570517) q0; }
gate unitary_134450573614960 q0 { u(0,-3.1414009059913073,3.141784401188279) q0; }
gate unitary_134450571792352 q0 { u(0,-0.00019174759848570517,-0.00019174759848570517) q0; }
gate unitary_134450627735632 q0 { u(0,-3.1414009059913073,3.141784401188279) q0; }
gate unitary_134450571195024 q0 { u(0,-pi/32768,-pi/32768) q0; }
gate unitary_134450627889200 q0 { u(0,-3.1414967797905504,3.141688527389036) q0; }
gate unitary_134450567482016 q0 { u(0,-pi/32768,-pi/32768) q0; }
gate unitary_134450567680496 q0 { u(0,-3.1414967797905504,3.141688527389036) q0; }
gate mcphase_134450567389088(param0) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { mcx_vchain_134450567689856 q0,q1,q2,q3,q4,q5,q6,q14,q7,q8,q9,q10,q11; unitary q14; mcx_vchain_134450567686736 q7,q8,q9,q10,q11,q12,q13,q14,q2,q3,q4,q5,q6; unitary_134450570841120 q14; mcx_vchain_134450567687120 q0,q1,q2,q3,q4,q5,q6,q14,q7,q8,q9,q10,q11; unitary q14; mcx_vchain_134450567684240 q7,q8,q9,q10,q11,q12,q13,q14,q2,q3,q4,q5,q6; unitary_134450570842464 q14; mcx_vchain_134450567487200 q0,q1,q2,q3,q4,q5,q6,q13,q7,q8,q9,q10,q11; unitary_134450629461248 q13; mcx_vchain_134450567488112 q7,q8,q9,q10,q11,q12,q13,q3,q4,q5,q6; unitary_134450570839392 q13; mcx_vchain_134450567484272 q0,q1,q2,q3,q4,q5,q6,q13,q7,q8,q9,q10,q11; unitary_134450570614384 q13; mcx_vchain_134450567494304 q7,q8,q9,q10,q11,q12,q13,q3,q4,q5,q6; unitary_134450570613760 q13; mcx_vchain_134450567976560 q0,q1,q2,q3,q4,q5,q12,q6,q7,q8,q9; unitary_134450570623792 q12; mcx_vchain_134450567690000 q6,q7,q8,q9,q10,q11,q12,q2,q3,q4,q5; unitary_134450570840928 q12; mcx_vchain_134450563376112 q0,q1,q2,q3,q4,q5,q12,q6,q7,q8,q9; unitary_134450572559328 q12; mcx_vchain_134450563376544 q6,q7,q8,q9,q10,q11,q12,q2,q3,q4,q5; unitary_134450572562928 q12; mcx_vchain_134450567494208 q0,q1,q2,q3,q4,q5,q11,q6,q7,q8,q9; unitary_134450572562688 q11; mcx_vchain_134450567493728 q6,q7,q8,q9,q10,q11,q3,q4,q5; unitary_134450572311920 q11; mcx_vchain_134450567490752 q0,q1,q2,q3,q4,q5,q11,q6,q7,q8,q9; unitary_134450572311392 q11; mcx_vchain_134450567493056 q6,q7,q8,q9,q10,q11,q3,q4,q5; unitary_134450572308080 q11; mcx_vchain_134450629151488 q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary_134450572298288 q10; mcx_vchain_134450567483552 q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450572232944 q10; mcx_vchain_134450567482256 q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary_134450570839776 q10; mcx_vchain_134450567480192 q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450572233040 q10; mcx_vchain_134450627006288 q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450572237600 q9; mcx_vchain_134450627412144 q5,q6,q7,q8,q9,q3,q4; unitary_134450572235344 q9; mcx_vchain_134450627005904 q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450572238512 q9; mcx_vchain_134450627006096 q5,q6,q7,q8,q9,q3,q4; unitary_134450633029440 q9; mcx_vchain_134450616022608 q0,q1,q2,q3,q8,q4,q5; unitary_134450573056464 q8; mcx_vchain_134450630171088 q4,q5,q6,q7,q8,q2,q3; unitary_134450573061024 q8; mcx_vchain_134450630167968 q0,q1,q2,q3,q8,q4,q5; unitary_134450571791728 q8; mcx_vchain_134450635253872 q4,q5,q6,q7,q8,q2,q3; unitary_134450571790048 q8; mcx_vchain_134450571183840 q0,q1,q2,q3,q7,q4,q5; unitary_134450571804352 q7; mcx_vchain_134450571184800 q4,q5,q6,q7,q3; unitary_134450571802816 q7; mcx_vchain_134450571186144 q0,q1,q2,q3,q7,q4,q5; unitary_134450571796192 q7; mcx_vchain_134450571185760 q4,q5,q6,q7,q3; unitary_134450573615008 q7; mcx_vchain_134450571188064 q0,q1,q2,q6,q3; unitary_134450573615920 q6; mcx_vchain_134450571191664 q3,q4,q5,q6,q2; unitary_134450571802864 q6; mcx_vchain_134450571196080 q0,q1,q2,q6,q3; unitary_134450573615344 q6; mcx_vchain_134450571193824 q3,q4,q5,q6,q2; unitary_134450573617744 q6; mcx_vchain_134450570847888 q0,q1,q2,q5,q3; unitary_134450573616352 q5; ccx q3,q4,q5; unitary_134450573281808 q5; mcx_vchain_134450570849760 q0,q1,q2,q5,q3; unitary_134450571796432 q5; ccx q3,q4,q5; unitary_134450573282720 q5; ccx q0,q1,q4; unitary_134450573280944 q4; ccx q2,q3,q4; unitary_134450573290496 q4; ccx q0,q1,q4; unitary_134450573287328 q4; ccx q2,q3,q4; unitary_134450573285600 q4; ccx q0,q1,q3; unitary_134450573280752 q3; cx q2,q3; unitary_134450573614960 q3; ccx q0,q1,q3; unitary_134450571792352 q3; cx q2,q3; unitary_134450627735632 q3; cx q0,q2; unitary_134450571195024 q2; cx q1,q2; unitary_134450627889200 q2; cx q0,q2; unitary_134450567482016 q2; cx q1,q2; unitary_134450567680496 q2; crz(pi/8192) q0,q1; p(pi/16384) q0; }
gate mcx q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { h q14; mcphase_134450567389088(pi) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; h q14; }
gate gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { mcphase(pi) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; h q14; h q13; h q12; h q11; h q10; h q9; h q8; h q7; h q6; h q5; h q4; h q3; h q2; h q1; h q0; x q0; x q1; x q2; x q3; x q4; x q5; x q6; x q7; x q8; x q9; x q10; x q11; x q12; x q13; x q14; h q14; mcx q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; h q14; x q0; x q1; x q2; x q3; x q4; x q5; x q6; x q7; x q8; x q9; x q10; x q11; x q12; x q13; x q14; h q0; h q1; h q2; h q3; h q4; h q5; h q6; h q7; h q8; h q9; h q10; h q11; h q12; h q13; h q14; }
gate gate_Q_134450561982224 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450567397104 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450573611456 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450567681936 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450567677760 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450563905680 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450572928080 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450572922848 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450572921936 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450574040032 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450574046992 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450574044400 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450571183936 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450572760592 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450572770912 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450563906544 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450571797440 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450574716384 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450574706496 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450574706544 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450574324704 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450574318128 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450574312272 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450573824544 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450573832608 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450573825696 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610151376 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610154592 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610156320 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450609233872 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450609240304 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610156464 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450574320672 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450574048816 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450609226240 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610860304 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610848208 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610859632 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610646208 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610636368 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610641600 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610990272 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610991472 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610720112 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610724384 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610730624 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612720064 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610509664 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450609232576 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610732592 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610510624 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450567485328 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610851184 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610994832 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450613723424 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450613729472 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450613723952 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611875968 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611864880 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611877408 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450572755984 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612163728 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612170880 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612171072 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612174528 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612161568 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450613074640 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612171360 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612161664 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612165504 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612160416 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450613072960 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450613067536 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450613066768 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611407232 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611406992 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611408960 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611406800 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611723616 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611722992 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611727792 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450616299552 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450616301184 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450616302144 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612962368 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612974560 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450613068448 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611406032 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611723952 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611720064 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612970144 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612969424 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450613186976 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610155312 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450613183856 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450614402032 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450614388448 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450614387152 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450614399920 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612566784 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612560112 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612565728 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612342272 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612347600 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612556896 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612342560 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450614400592 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612968896 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610857808 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612319680 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450613185008 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612316992 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611525040 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611519808 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611521056 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611527968 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450573820656 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612833840 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612840800 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610503952 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612042160 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612038656 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612028096 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612034960 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612036208 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450572922128 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611410160 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611529600 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450613325696 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450613326416 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450613323008 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450613324160 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611199616 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610990752 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450574312992 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612320592 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611200048 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611918832 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450612029392 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450611915376 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450574711776 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
gate gate_Q_134450610650480 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14,q15; }
qreg q[15];
qreg flag[1];
creg meas[16];
h q[0];
h q[1];
h q[2];
h q[3];
h q[4];
h q[5];
h q[6];
h q[7];
h q[8];
h q[9];
h q[10];
h q[11];
h q[12];
h q[13];
h q[14];
x flag[0];
gate_Q_134450561982224 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450567397104 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450573611456 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450567681936 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450567677760 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450563905680 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450572928080 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450572922848 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450572921936 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450574040032 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450574046992 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450574044400 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450571183936 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450572760592 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450572770912 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450563906544 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450571797440 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450574716384 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450574706496 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450574706544 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450574324704 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450574318128 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450574312272 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450573824544 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450573832608 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450573825696 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610151376 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610154592 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610156320 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450609233872 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450609240304 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610156464 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450574320672 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450574048816 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450609226240 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610860304 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610848208 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610859632 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610646208 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610636368 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610641600 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610990272 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610991472 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610720112 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610724384 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610730624 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612720064 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610509664 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450609232576 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610732592 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610510624 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450567485328 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610851184 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610994832 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450613723424 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450613729472 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450613723952 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611875968 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611864880 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611877408 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450572755984 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612163728 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612170880 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612171072 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612174528 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612161568 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450613074640 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612171360 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612161664 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612165504 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612160416 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450613072960 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450613067536 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450613066768 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611407232 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611406992 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611408960 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611406800 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611723616 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611722992 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611727792 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450616299552 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450616301184 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450616302144 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612962368 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612974560 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450613068448 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611406032 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611723952 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611720064 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612970144 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612969424 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450613186976 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610155312 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450613183856 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450614402032 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450614388448 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450614387152 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450614399920 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612566784 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612560112 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612565728 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612342272 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612347600 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612556896 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612342560 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450614400592 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612968896 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610857808 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612319680 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450613185008 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612316992 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611525040 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611519808 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611521056 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611527968 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450573820656 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612833840 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612840800 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610503952 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612042160 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612038656 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612028096 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612034960 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612036208 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450572922128 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611410160 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611529600 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450613325696 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450613326416 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450613323008 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450613324160 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611199616 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610990752 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450574312992 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612320592 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611200048 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611918832 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450612029392 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450611915376 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450574711776 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
gate_Q_134450610650480 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
barrier q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],q[14],flag[0];
measure q[0] -> meas[0];
measure q[1] -> meas[1];
measure q[2] -> meas[2];
measure q[3] -> meas[3];
measure q[4] -> meas[4];
measure q[5] -> meas[5];
measure q[6] -> meas[6];
measure q[7] -> meas[7];
measure q[8] -> meas[8];
measure q[9] -> meas[9];
measure q[10] -> meas[10];
measure q[11] -> meas[11];
measure q[12] -> meas[12];
measure q[13] -> meas[13];
measure q[14] -> meas[14];
measure flag[0] -> meas[15];