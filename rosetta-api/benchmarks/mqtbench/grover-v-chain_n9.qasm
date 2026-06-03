OPENQASM 2.0;
include "qelib1.inc";
gate mcx_vchain q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary q0 { u(0,-pi/8,-pi/8) q0; }
gate unitary_134450461895008 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450494279696 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450462558784 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450460834944 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450463593472 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate unitary_134450463594048 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450460828464 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450463213376 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450461185888 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450463589392 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450461190448 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450488622256 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450461184160 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450629158496 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450461186704 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450611529120 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450462564400 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450457186416 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450488607280 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450460835184 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450611533680 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450613586832 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate unitary_134450613597776 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450613589904 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate unitary_134450611122544 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450627729776 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate unitary_134450504363056 q0 { u(0,-pi/256,-pi/256) q0; }
gate unitary_134450488615728 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate unitary_134450463215584 q0 { u(0,-pi/256,-pi/256) q0; }
gate unitary_134450462567232 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate unitary_134450460827936 q0 { u(0,-pi/512,-pi/512) q0; }
gate unitary_134450461180752 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate unitary_134450488370736 q0 { u(0,-pi/512,-pi/512) q0; }
gate unitary_134450459511744 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate mcphase(param0) q0,q1,q2,q3,q4,q5,q6,q7,q8 { mcx_vchain q0,q1,q2,q3,q8,q4,q5; unitary q8; mcx_vchain q4,q5,q6,q7,q8,q2,q3; unitary_134450461895008 q8; mcx_vchain q0,q1,q2,q3,q8,q4,q5; unitary q8; mcx_vchain q4,q5,q6,q7,q8,q2,q3; unitary_134450494279696 q8; mcx_vchain q0,q1,q2,q3,q7,q4,q5; unitary_134450462558784 q7; mcx_vchain_134450460834944 q4,q5,q6,q7,q3; unitary_134450463593472 q7; mcx_vchain q0,q1,q2,q3,q7,q4,q5; unitary_134450463594048 q7; mcx_vchain_134450460828464 q4,q5,q6,q7,q3; unitary_134450463213376 q7; mcx_vchain_134450461185888 q0,q1,q2,q6,q3; unitary_134450463589392 q6; mcx_vchain_134450461190448 q3,q4,q5,q6,q2; unitary_134450488622256 q6; mcx_vchain_134450461184160 q0,q1,q2,q6,q3; unitary_134450629158496 q6; mcx_vchain_134450461186704 q3,q4,q5,q6,q2; unitary_134450611529120 q6; mcx_vchain_134450462564400 q0,q1,q2,q5,q3; unitary_134450457186416 q5; ccx q3,q4,q5; unitary_134450488607280 q5; mcx_vchain_134450460835184 q0,q1,q2,q5,q3; unitary_134450611533680 q5; ccx q3,q4,q5; unitary_134450613586832 q5; ccx q0,q1,q4; unitary_134450613597776 q4; ccx q2,q3,q4; unitary_134450613589904 q4; ccx q0,q1,q4; unitary_134450611122544 q4; ccx q2,q3,q4; unitary_134450627729776 q4; ccx q0,q1,q3; unitary_134450504363056 q3; cx q2,q3; unitary_134450488615728 q3; ccx q0,q1,q3; unitary_134450463215584 q3; cx q2,q3; unitary_134450462567232 q3; cx q0,q2; unitary_134450460827936 q2; cx q1,q2; unitary_134450461180752 q2; cx q0,q2; unitary_134450488370736 q2; cx q1,q2; unitary_134450459511744 q2; crz(pi/128) q0,q1; p(pi/256) q0; }
gate mcx_vchain_134450574048240 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { rccx q0,q1,q8; rccx q2,q8,q9; rccx q3,q9,q10; rccx q4,q10,q11; rccx q5,q11,q12; ccx q6,q12,q7; rccx q5,q11,q12; rccx q4,q10,q11; rccx q3,q9,q10; rccx q2,q8,q9; rccx q0,q1,q8; }
gate gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { mcphase(pi) q0,q1,q2,q3,q4,q5,q6,q7,q8; h q7; h q6; h q5; h q4; h q3; h q2; h q1; h q0; x q0; x q1; x q2; x q3; x q4; x q5; x q6; x q7; h q7; mcx_vchain_134450574048240 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; h q7; x q0; x q1; x q2; x q3; x q4; x q5; x q6; x q7; h q0; h q1; h q2; h q3; h q4; h q5; h q6; h q7; }
gate gate_Q_134450504305840 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450610562560 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450461190640 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450613588080 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450459431504 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450492714848 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450567975312 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450496271472 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450551981360 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450574047856 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450488263216 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450488269408 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
qreg q[12];
qreg flag[1];
creg meas[13];
h q[0];
h q[1];
h q[2];
h q[3];
h q[4];
h q[5];
h q[6];
h q[7];
x q[8];
gate_Q_134450504305840 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450610562560 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450461190640 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450613588080 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450459431504 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450492714848 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450567975312 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450496271472 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450551981360 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450574047856 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450488263216 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450488269408 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
barrier q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
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
measure flag[0] -> meas[12];