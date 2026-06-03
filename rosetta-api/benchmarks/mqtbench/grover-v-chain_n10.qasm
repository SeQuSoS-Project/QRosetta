OPENQASM 2.0;
include "qelib1.inc";
gate mcx_vchain q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary q0 { u(0,-pi/8,-pi/8) q0; }
gate mcx_vchain_134450610723712 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450610158720 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450610730480 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450610145184 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450459851664 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450610150800 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450492531024 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450610145712 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450610720976 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450459844992 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450610732400 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450556027776 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450459197904 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450556030992 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450459198384 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450556038624 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450459207216 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450610148784 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450459211920 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450556028928 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450502281232 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450556036752 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450502281136 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450556027872 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450502285408 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610148832 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450502279744 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450556027440 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450610147440 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450556029408 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450556043232 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450610146144 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450556032288 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450610729712 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate unitary_134450556030896 q0 { u(0,-pi/256,-pi/256) q0; }
gate unitary_134450556039968 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate unitary_134450556030512 q0 { u(0,-pi/256,-pi/256) q0; }
gate unitary_134450556028640 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate unitary_134450562347040 q0 { u(0,-pi/512,-pi/512) q0; }
gate unitary_134450562336432 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate unitary_134450562335760 q0 { u(0,-pi/512,-pi/512) q0; }
gate unitary_134450556029120 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate unitary_134450562345360 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate unitary_134450462564544 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate unitary_134450562346416 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate unitary_134450562349392 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate mcphase(param0) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9 { mcx_vchain q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary q9; mcx_vchain_134450610723712 q5,q6,q7,q8,q9,q3,q4; unitary_134450610158720 q9; mcx_vchain q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary q9; mcx_vchain_134450610730480 q5,q6,q7,q8,q9,q3,q4; unitary_134450610145184 q9; mcx_vchain_134450459851664 q0,q1,q2,q3,q8,q4,q5; unitary_134450610150800 q8; mcx_vchain_134450492531024 q4,q5,q6,q7,q8,q2,q3; unitary_134450610145712 q8; mcx_vchain_134450610720976 q0,q1,q2,q3,q8,q4,q5; unitary_134450459844992 q8; mcx_vchain_134450610732400 q4,q5,q6,q7,q8,q2,q3; unitary_134450556027776 q8; mcx_vchain_134450459197904 q0,q1,q2,q3,q7,q4,q5; unitary_134450556030992 q7; mcx_vchain_134450459198384 q4,q5,q6,q7,q3; unitary_134450556038624 q7; mcx_vchain_134450459207216 q0,q1,q2,q3,q7,q4,q5; unitary_134450610148784 q7; mcx_vchain_134450459211920 q4,q5,q6,q7,q3; unitary_134450556028928 q7; mcx_vchain_134450502281232 q0,q1,q2,q6,q3; unitary_134450556036752 q6; mcx_vchain_134450502281136 q3,q4,q5,q6,q2; unitary_134450556027872 q6; mcx_vchain_134450502285408 q0,q1,q2,q6,q3; unitary_134450610148832 q6; mcx_vchain_134450502279744 q3,q4,q5,q6,q2; unitary_134450556027440 q6; mcx_vchain_134450610147440 q0,q1,q2,q5,q3; unitary_134450556029408 q5; ccx q3,q4,q5; unitary_134450556043232 q5; mcx_vchain_134450610146144 q0,q1,q2,q5,q3; unitary_134450556032288 q5; ccx q3,q4,q5; unitary_134450610729712 q5; ccx q0,q1,q4; unitary_134450556030896 q4; ccx q2,q3,q4; unitary_134450556039968 q4; ccx q0,q1,q4; unitary_134450556030512 q4; ccx q2,q3,q4; unitary_134450556028640 q4; ccx q0,q1,q3; unitary_134450562347040 q3; cx q2,q3; unitary_134450562336432 q3; ccx q0,q1,q3; unitary_134450562335760 q3; cx q2,q3; unitary_134450556029120 q3; cx q0,q2; unitary_134450562345360 q2; cx q1,q2; unitary_134450462564544 q2; cx q0,q2; unitary_134450562346416 q2; cx q1,q2; unitary_134450562349392 q2; crz(pi/256) q0,q1; p(pi/512) q0; }
gate mcx_vchain_134450573608480 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { rccx q0,q1,q9; rccx q2,q9,q10; rccx q3,q10,q11; rccx q4,q11,q12; rccx q5,q12,q13; rccx q6,q13,q14; ccx q7,q14,q8; rccx q6,q13,q14; rccx q5,q12,q13; rccx q4,q11,q12; rccx q3,q10,q11; rccx q2,q9,q10; rccx q0,q1,q9; }
gate gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { mcphase(pi) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9; h q8; h q7; h q6; h q5; h q4; h q3; h q2; h q1; h q0; x q0; x q1; x q2; x q3; x q4; x q5; x q6; x q7; x q8; h q8; mcx_vchain_134450573608480 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; h q8; x q0; x q1; x q2; x q3; x q4; x q5; x q6; x q7; x q8; h q0; h q1; h q2; h q3; h q4; h q5; h q6; h q7; h q8; }
gate gate_Q_134450613588080 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450459514912 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450570610400 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450502702608 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450573614672 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450556037280 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450610727744 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450610148352 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450562337680 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450556027392 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450459510112 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450562343872 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450562349344 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450561407632 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450556039824 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450561416752 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
gate gate_Q_134450561404848 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12,q13,q14; }
qreg q[14];
qreg flag[1];
creg meas[15];
h q[0];
h q[1];
h q[2];
h q[3];
h q[4];
h q[5];
h q[6];
h q[7];
h q[8];
x q[9];
gate_Q_134450613588080 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450459514912 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450570610400 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450502702608 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450573614672 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450556037280 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450610727744 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450610148352 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450562337680 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450556027392 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450459510112 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450562343872 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450562349344 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450561407632 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450556039824 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450561416752 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
gate_Q_134450561404848 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
barrier q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],q[12],q[13],flag[0];
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
measure flag[0] -> meas[14];