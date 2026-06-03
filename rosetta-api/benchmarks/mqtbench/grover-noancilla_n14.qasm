OPENQASM 2.0;
include "qelib1.inc";
gate mcx_vchain q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; ccx q6,q12,q7; h q12; t q12; cx q5,q12; tdg q12; cx q11,q12; h q11; t q11; cx q4,q11; tdg q11; cx q10,q11; h q10; t q10; cx q3,q10; tdg q10; cx q9,q10; h q9; t q9; cx q2,q9; tdg q9; cx q8,q9; h q8; t q8; cx q0,q8; tdg q8; cx q1,q8; t q8; cx q0,q8; tdg q8; h q8; cx q8,q9; t q9; cx q2,q9; tdg q9; h q9; cx q9,q10; t q10; cx q3,q10; tdg q10; h q10; cx q10,q11; t q11; cx q4,q11; tdg q11; h q11; cx q11,q12; t q12; cx q5,q12; tdg q12; h q12; }
gate unitary q0 { u(0,-pi/8,-pi/8) q0; }
gate mcx_vchain_134450612555504 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450613599168 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450612555312 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450612554352 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450628640496 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450616302624 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450612310704 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450612557136 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450627899136 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450613337552 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450628637568 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450613593216 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450615623344 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450613588896 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450627006288 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450572570272 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450627008016 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450627425440 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450627006096 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450616300752 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450616303200 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450612554544 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450616301232 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450612553968 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450616300032 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450611924400 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450616303104 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450613185680 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450616300128 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450613584912 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450616301184 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450613593984 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450616297296 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450613591008 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450616299264 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450610504048 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450616301280 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450613588272 q0 { u(0,-pi/256,-pi/256) q0; }
gate mcx_vchain_134450616302240 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450613587792 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcx_vchain_134450616301376 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450613587744 q0 { u(0,-pi/256,-pi/256) q0; }
gate mcx_vchain_134450616302144 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450613592064 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcx_vchain_134450613586784 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450611726544 q0 { u(0,-pi/512,-pi/512) q0; }
gate mcx_vchain_134450613586304 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450613592016 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate mcx_vchain_134450613586400 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450627150960 q0 { u(0,-pi/512,-pi/512) q0; }
gate mcx_vchain_134450613586496 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450629151488 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate mcx_vchain_134450613596336 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450614388112 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate mcx_vchain_134450613594704 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450613597872 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate mcx_vchain_134450613594800 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450614388928 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate mcx_vchain_134450613594896 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450614399872 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate mcx_vchain_134450616300080 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450614397760 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate unitary_134450614402272 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate mcx_vchain_134450616298928 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450614396896 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate unitary_134450614388448 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate unitary_134450614397232 q0 { u(0,-pi/4096,-pi/4096) q0; }
gate unitary_134450614394784 q0 { u(0,-3.14082566319585,3.142359643983736) q0; }
gate unitary_134450614394064 q0 { u(0,-pi/4096,-pi/4096) q0; }
gate unitary_134450614395888 q0 { u(0,-3.14082566319585,3.142359643983736) q0; }
gate unitary_134450614393248 q0 { u(0,-pi/8192,-pi/8192) q0; }
gate unitary_134450614395408 q0 { u(0,-3.141209158392822,3.1419761487867643) q0; }
gate unitary_134450614394352 q0 { u(0,-pi/8192,-pi/8192) q0; }
gate unitary_134450614395840 q0 { u(0,-3.141209158392822,3.1419761487867643) q0; }
gate unitary_134450614390800 q0 { u(0,-0.00019174759848570517,-0.00019174759848570517) q0; }
gate unitary_134450613718864 q0 { u(0,-3.1414009059913073,3.141784401188279) q0; }
gate unitary_134450613730864 q0 { u(0,-0.00019174759848570517,-0.00019174759848570517) q0; }
gate unitary_134450613729568 q0 { u(0,-3.1414009059913073,3.141784401188279) q0; }
gate mcphase(param0) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { mcx_vchain q0,q1,q2,q3,q4,q5,q6,q13,q7,q8,q9,q10,q11; unitary q13; mcx_vchain_134450612555504 q7,q8,q9,q10,q11,q12,q13,q3,q4,q5,q6; unitary_134450613599168 q13; mcx_vchain q0,q1,q2,q3,q4,q5,q6,q13,q7,q8,q9,q10,q11; unitary q13; mcx_vchain_134450612555312 q7,q8,q9,q10,q11,q12,q13,q3,q4,q5,q6; unitary_134450612554352 q13; mcx_vchain_134450628640496 q0,q1,q2,q3,q4,q5,q12,q6,q7,q8,q9; unitary_134450616302624 q12; mcx_vchain_134450612310704 q6,q7,q8,q9,q10,q11,q12,q2,q3,q4,q5; unitary_134450612557136 q12; mcx_vchain_134450627899136 q0,q1,q2,q3,q4,q5,q12,q6,q7,q8,q9; unitary_134450613337552 q12; mcx_vchain_134450628637568 q6,q7,q8,q9,q10,q11,q12,q2,q3,q4,q5; unitary_134450613593216 q12; mcx_vchain_134450615623344 q0,q1,q2,q3,q4,q5,q11,q6,q7,q8,q9; unitary_134450613588896 q11; mcx_vchain_134450627006288 q6,q7,q8,q9,q10,q11,q3,q4,q5; unitary_134450572570272 q11; mcx_vchain_134450627008016 q0,q1,q2,q3,q4,q5,q11,q6,q7,q8,q9; unitary_134450627425440 q11; mcx_vchain_134450627006096 q6,q7,q8,q9,q10,q11,q3,q4,q5; unitary_134450616300752 q11; mcx_vchain_134450616303200 q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary_134450612554544 q10; mcx_vchain_134450616301232 q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450612553968 q10; mcx_vchain_134450616300032 q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary_134450611924400 q10; mcx_vchain_134450616303104 q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450613185680 q10; mcx_vchain_134450616300128 q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450613584912 q9; mcx_vchain_134450616301184 q5,q6,q7,q8,q9,q3,q4; unitary_134450613593984 q9; mcx_vchain_134450616297296 q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450613591008 q9; mcx_vchain_134450616299264 q5,q6,q7,q8,q9,q3,q4; unitary_134450610504048 q9; mcx_vchain_134450616301280 q0,q1,q2,q3,q8,q4,q5; unitary_134450613588272 q8; mcx_vchain_134450616302240 q4,q5,q6,q7,q8,q2,q3; unitary_134450613587792 q8; mcx_vchain_134450616301376 q0,q1,q2,q3,q8,q4,q5; unitary_134450613587744 q8; mcx_vchain_134450616302144 q4,q5,q6,q7,q8,q2,q3; unitary_134450613592064 q8; mcx_vchain_134450613586784 q0,q1,q2,q3,q7,q4,q5; unitary_134450611726544 q7; mcx_vchain_134450613586304 q4,q5,q6,q7,q3; unitary_134450613592016 q7; mcx_vchain_134450613586400 q0,q1,q2,q3,q7,q4,q5; unitary_134450627150960 q7; mcx_vchain_134450613586496 q4,q5,q6,q7,q3; unitary_134450629151488 q7; mcx_vchain_134450613596336 q0,q1,q2,q6,q3; unitary_134450614388112 q6; mcx_vchain_134450613594704 q3,q4,q5,q6,q2; unitary_134450613597872 q6; mcx_vchain_134450613594800 q0,q1,q2,q6,q3; unitary_134450614388928 q6; mcx_vchain_134450613594896 q3,q4,q5,q6,q2; unitary_134450614399872 q6; mcx_vchain_134450616300080 q0,q1,q2,q5,q3; unitary_134450614397760 q5; ccx q3,q4,q5; unitary_134450614402272 q5; mcx_vchain_134450616298928 q0,q1,q2,q5,q3; unitary_134450614396896 q5; ccx q3,q4,q5; unitary_134450614388448 q5; ccx q0,q1,q4; unitary_134450614397232 q4; ccx q2,q3,q4; unitary_134450614394784 q4; ccx q0,q1,q4; unitary_134450614394064 q4; ccx q2,q3,q4; unitary_134450614395888 q4; ccx q0,q1,q3; unitary_134450614393248 q3; cx q2,q3; unitary_134450614395408 q3; ccx q0,q1,q3; unitary_134450614394352 q3; cx q2,q3; unitary_134450614395840 q3; cx q0,q2; unitary_134450614390800 q2; cx q1,q2; unitary_134450613718864 q2; cx q0,q2; unitary_134450613730864 q2; cx q1,q2; unitary_134450613729568 q2; crz(pi/4096) q0,q1; p(pi/8192) q0; }
gate mcx_vchain_134450613723376 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate mcx_vchain_134450613722848 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450571198240 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450613722608 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate mcx_vchain_134450613724672 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450567481632 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450571183456 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450571187296 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450571182448 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450571190032 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450571183504 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary_134450567480288 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450571187440 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450567482112 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450571186912 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450567483792 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450571183360 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450567484128 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450571183264 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450567484464 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450571187104 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450567485184 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450571188976 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450567486480 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450571188592 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450567480144 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450571188688 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450567487392 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450571188784 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450567487344 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450571190896 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450567489648 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450571190512 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450567490368 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450571190608 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450567489024 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450571190704 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450571190464 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450571192912 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450571193968 q0 { u(0,-pi/256,-pi/256) q0; }
gate mcx_vchain_134450571192528 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450613722032 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcx_vchain_134450571192624 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450613726352 q0 { u(0,-pi/256,-pi/256) q0; }
gate mcx_vchain_134450571192720 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450614388496 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcx_vchain_134450613593696 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450571186528 q0 { u(0,-pi/512,-pi/512) q0; }
gate mcx_vchain_134450611192752 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450613589616 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate mcx_vchain_134450613721408 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450567490848 q0 { u(0,-pi/512,-pi/512) q0; }
gate mcx_vchain_134450613726832 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450567490608 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate mcx_vchain_134450571192144 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450611717904 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate unitary_134450571185712 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate mcx_vchain_134450571190800 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450567487536 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate unitary_134450567494112 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate unitary_134450567494304 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate unitary_134450567676032 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate unitary_134450567676608 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate unitary_134450567495360 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate unitary_134450567482928 q0 { u(0,-pi/4096,-pi/4096) q0; }
gate unitary_134450567676944 q0 { u(0,-3.14082566319585,3.142359643983736) q0; }
gate unitary_134450567676368 q0 { u(0,-pi/4096,-pi/4096) q0; }
gate unitary_134450567678480 q0 { u(0,-3.14082566319585,3.142359643983736) q0; }
gate unitary_134450567677232 q0 { u(0,-pi/8192,-pi/8192) q0; }
gate unitary_134450567679728 q0 { u(0,-3.141209158392822,3.1419761487867643) q0; }
gate unitary_134450567680640 q0 { u(0,-pi/8192,-pi/8192) q0; }
gate unitary_134450614396416 q0 { u(0,-3.141209158392822,3.1419761487867643) q0; }
gate mcphase_134450612168576(param0) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { mcx_vchain_134450613723376 q0,q1,q2,q3,q4,q5,q12,q6,q7,q8,q9; unitary q12; mcx_vchain_134450613722848 q6,q7,q8,q9,q10,q11,q12,q2,q3,q4,q5; unitary_134450571198240 q12; mcx_vchain_134450613722608 q0,q1,q2,q3,q4,q5,q12,q6,q7,q8,q9; unitary q12; mcx_vchain_134450613724672 q6,q7,q8,q9,q10,q11,q12,q2,q3,q4,q5; unitary_134450567481632 q12; mcx_vchain_134450571183456 q0,q1,q2,q3,q4,q5,q11,q6,q7,q8,q9; unitary_134450571187296 q11; mcx_vchain_134450571182448 q6,q7,q8,q9,q10,q11,q3,q4,q5; unitary_134450571190032 q11; mcx_vchain_134450571183504 q0,q1,q2,q3,q4,q5,q11,q6,q7,q8,q9; unitary_134450567480288 q11; mcx_vchain_134450571187440 q6,q7,q8,q9,q10,q11,q3,q4,q5; unitary_134450567482112 q11; mcx_vchain_134450571186912 q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary_134450567483792 q10; mcx_vchain_134450571183360 q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450567484128 q10; mcx_vchain_134450571183264 q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary_134450567484464 q10; mcx_vchain_134450571187104 q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450567485184 q10; mcx_vchain_134450571188976 q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450567486480 q9; mcx_vchain_134450571188592 q5,q6,q7,q8,q9,q3,q4; unitary_134450567480144 q9; mcx_vchain_134450571188688 q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450567487392 q9; mcx_vchain_134450571188784 q5,q6,q7,q8,q9,q3,q4; unitary_134450567487344 q9; mcx_vchain_134450571190896 q0,q1,q2,q3,q8,q4,q5; unitary_134450567489648 q8; mcx_vchain_134450571190512 q4,q5,q6,q7,q8,q2,q3; unitary_134450567490368 q8; mcx_vchain_134450571190608 q0,q1,q2,q3,q8,q4,q5; unitary_134450567489024 q8; mcx_vchain_134450571190704 q4,q5,q6,q7,q8,q2,q3; unitary_134450571190464 q8; mcx_vchain_134450571192912 q0,q1,q2,q3,q7,q4,q5; unitary_134450571193968 q7; mcx_vchain_134450571192528 q4,q5,q6,q7,q3; unitary_134450613722032 q7; mcx_vchain_134450571192624 q0,q1,q2,q3,q7,q4,q5; unitary_134450613726352 q7; mcx_vchain_134450571192720 q4,q5,q6,q7,q3; unitary_134450614388496 q7; mcx_vchain_134450613593696 q0,q1,q2,q6,q3; unitary_134450571186528 q6; mcx_vchain_134450611192752 q3,q4,q5,q6,q2; unitary_134450613589616 q6; mcx_vchain_134450613721408 q0,q1,q2,q6,q3; unitary_134450567490848 q6; mcx_vchain_134450613726832 q3,q4,q5,q6,q2; unitary_134450567490608 q6; mcx_vchain_134450571192144 q0,q1,q2,q5,q3; unitary_134450611717904 q5; ccx q3,q4,q5; unitary_134450571185712 q5; mcx_vchain_134450571190800 q0,q1,q2,q5,q3; unitary_134450567487536 q5; ccx q3,q4,q5; unitary_134450567494112 q5; ccx q0,q1,q4; unitary_134450567494304 q4; ccx q2,q3,q4; unitary_134450567676032 q4; ccx q0,q1,q4; unitary_134450567676608 q4; ccx q2,q3,q4; unitary_134450567495360 q4; ccx q0,q1,q3; unitary_134450567482928 q3; cx q2,q3; unitary_134450567676944 q3; ccx q0,q1,q3; unitary_134450567676368 q3; cx q2,q3; unitary_134450567678480 q3; cx q0,q2; unitary_134450567677232 q2; cx q1,q2; unitary_134450567679728 q2; cx q0,q2; unitary_134450567680640 q2; cx q1,q2; unitary_134450614396416 q2; crz(pi/2048) q0,q1; p(pi/4096) q0; }
gate mcx q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { h q12; mcphase_134450612168576(pi) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; h q12; }
gate gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { mcphase(pi) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; h q12; h q11; h q10; h q9; h q8; h q7; h q6; h q5; h q4; h q3; h q2; h q1; h q0; x q0; x q1; x q2; x q3; x q4; x q5; x q6; x q7; x q8; x q9; x q10; x q11; x q12; h q12; mcx q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; h q12; x q0; x q1; x q2; x q3; x q4; x q5; x q6; x q7; x q8; x q9; x q10; x q11; x q12; h q0; h q1; h q2; h q3; h q4; h q5; h q6; h q7; h q8; h q9; h q10; h q11; h q12; }
gate gate_Q_134450612566544 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450613716032 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450571195792 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450571195744 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450612562128 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450612560688 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567684624 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567687168 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567688224 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567687744 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567690144 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567692160 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567975504 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567975024 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450611877648 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450614394112 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567493488 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567684192 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567686304 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567982704 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567976848 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567984288 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567986304 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567984864 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450568206080 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450568207280 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450568209680 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450568208960 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450568203536 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450568211552 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450568200992 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567491280 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566419648 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566421376 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450568209872 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450568211888 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567688896 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567981744 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567984480 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566424832 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566424928 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566426800 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566426896 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566627648 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566632112 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566634320 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566636624 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566636000 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566640560 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566641616 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566643488 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566643248 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566909296 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566911840 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566914432 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566638736 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566415424 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567979392 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566636960 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566637968 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567986496 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566909584 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566919232 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450566917792 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567104752 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567107344 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567102784 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567111616 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567972912 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567114448 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
gate gate_Q_134450567113440 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13; }
qreg q[13];
qreg flag[1];
creg meas[14];
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
x flag[0];
gate_Q_134450612566544 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450613716032 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450571195792 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450571195744 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450612562128 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450612560688 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567684624 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567687168 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567688224 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567687744 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567690144 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567692160 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567975504 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567975024 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450611877648 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450614394112 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567493488 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567684192 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567686304 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567982704 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567976848 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567984288 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567986304 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567984864 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450568206080 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450568207280 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450568209680 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450568208960 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450568203536 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450568211552 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450568200992 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567491280 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566419648 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566421376 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450568209872 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450568211888 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567688896 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567981744 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567984480 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566424832 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566424928 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566426800 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566426896 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566627648 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566632112 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566634320 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566636624 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566636000 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566640560 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566641616 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566643488 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566643248 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566909296 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566911840 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566914432 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566638736 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566415424 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567979392 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566636960 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566637968 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567986496 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566909584 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566919232 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450566917792 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567104752 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567107344 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567102784 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567111616 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567972912 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567114448 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
gate_Q_134450567113440 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
barrier q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],flag[0];
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
measure flag[0] -> meas[13];