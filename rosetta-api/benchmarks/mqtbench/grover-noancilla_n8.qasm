OPENQASM 2.0;
include "qelib1.inc";
gate mcx_vchain q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary q0 { u(0,-pi/8,-pi/8) q0; }
gate mcx_vchain_134450611717232 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450612345008 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450611718912 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450613065232 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450614399872 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450613074784 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450612835952 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450613063504 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450612669136 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450613073392 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450614393104 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450613061296 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450611526960 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450611867856 q0 { u(0,-pi/32,-pi/32) q0; }
gate unitary_134450611872704 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450611531376 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450611878176 q0 { u(0,-pi/32,-pi/32) q0; }
gate unitary_134450613063408 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate unitary_134450611877696 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450611876016 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate unitary_134450611870640 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450611873328 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate unitary_134450611875632 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450611878224 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate unitary_134450612307344 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450611879472 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate unitary_134450611871840 q0 { u(0,-pi/256,-pi/256) q0; }
gate unitary_134450611869824 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate unitary_134450611866368 q0 { u(0,-pi/256,-pi/256) q0; }
gate unitary_134450611865552 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcphase(param0) q0,q1,q2,q3,q4,q5,q6,q7 { mcx_vchain q0,q1,q2,q3,q7,q4,q5; unitary q7; mcx_vchain_134450611717232 q4,q5,q6,q7,q3; unitary_134450612345008 q7; mcx_vchain q0,q1,q2,q3,q7,q4,q5; unitary q7; mcx_vchain_134450611718912 q4,q5,q6,q7,q3; unitary_134450613065232 q7; mcx_vchain_134450614399872 q0,q1,q2,q6,q3; unitary_134450613074784 q6; mcx_vchain_134450612835952 q3,q4,q5,q6,q2; unitary_134450613063504 q6; mcx_vchain_134450612669136 q0,q1,q2,q6,q3; unitary_134450613073392 q6; mcx_vchain_134450614393104 q3,q4,q5,q6,q2; unitary_134450613061296 q6; mcx_vchain_134450611526960 q0,q1,q2,q5,q3; unitary_134450611867856 q5; ccx q3,q4,q5; unitary_134450611872704 q5; mcx_vchain_134450611531376 q0,q1,q2,q5,q3; unitary_134450611878176 q5; ccx q3,q4,q5; unitary_134450613063408 q5; ccx q0,q1,q4; unitary_134450611877696 q4; ccx q2,q3,q4; unitary_134450611876016 q4; ccx q0,q1,q4; unitary_134450611870640 q4; ccx q2,q3,q4; unitary_134450611873328 q4; ccx q0,q1,q3; unitary_134450611875632 q3; cx q2,q3; unitary_134450611878224 q3; ccx q0,q1,q3; unitary_134450612307344 q3; cx q2,q3; unitary_134450611879472 q3; cx q0,q2; unitary_134450611871840 q2; cx q1,q2; unitary_134450611869824 q2; cx q0,q2; unitary_134450611866368 q2; cx q1,q2; unitary_134450611865552 q2; crz(pi/64) q0,q1; p(pi/128) q0; }
gate mcx_vchain_134450611873760 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate mcx_vchain_134450611868672 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450613728320 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450611868768 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate mcx_vchain_134450611873568 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450612348128 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450613730336 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450613725488 q0 { u(0,-pi/16,-pi/16) q0; }
gate unitary_134450613721456 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450613723520 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610556512 q0 { u(0,-pi/16,-pi/16) q0; }
gate unitary_134450610558192 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate unitary_134450610556944 q0 { u(0,-pi/32,-pi/32) q0; }
gate unitary_134450611879760 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate unitary_134450610557712 q0 { u(0,-pi/32,-pi/32) q0; }
gate unitary_134450610555120 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate unitary_134450610557040 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450610558528 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate unitary_134450610559968 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450610560112 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate unitary_134450611410208 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450610557232 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate unitary_134450610562080 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450610563376 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcphase_134450611878512(param0) q0,q1,q2,q3,q4,q5,q6 { mcx_vchain_134450611873760 q0,q1,q2,q6,q3; unitary q6; mcx_vchain_134450611868672 q3,q4,q5,q6,q2; unitary_134450613728320 q6; mcx_vchain_134450611868768 q0,q1,q2,q6,q3; unitary q6; mcx_vchain_134450611873568 q3,q4,q5,q6,q2; unitary_134450612348128 q6; mcx_vchain_134450613730336 q0,q1,q2,q5,q3; unitary_134450613725488 q5; ccx q3,q4,q5; unitary_134450613721456 q5; mcx_vchain_134450613723520 q0,q1,q2,q5,q3; unitary_134450610556512 q5; ccx q3,q4,q5; unitary_134450610558192 q5; ccx q0,q1,q4; unitary_134450610556944 q4; ccx q2,q3,q4; unitary_134450611879760 q4; ccx q0,q1,q4; unitary_134450610557712 q4; ccx q2,q3,q4; unitary_134450610555120 q4; ccx q0,q1,q3; unitary_134450610557040 q3; cx q2,q3; unitary_134450610558528 q3; ccx q0,q1,q3; unitary_134450610559968 q3; cx q2,q3; unitary_134450610560112 q3; cx q0,q2; unitary_134450611410208 q2; cx q1,q2; unitary_134450610557232 q2; cx q0,q2; unitary_134450610562080 q2; cx q1,q2; unitary_134450610563376 q2; crz(pi/32) q0,q1; p(pi/64) q0; }
gate mcx q0,q1,q2,q3,q4,q5,q6 { h q6; mcphase_134450611878512(pi) q0,q1,q2,q3,q4,q5,q6; h q6; }
gate gate_Q q0,q1,q2,q3,q4,q5,q6,q7 { mcphase(pi) q0,q1,q2,q3,q4,q5,q6,q7; h q6; h q5; h q4; h q3; h q2; h q1; h q0; x q0; x q1; x q2; x q3; x q4; x q5; x q6; h q6; mcx q0,q1,q2,q3,q4,q5,q6; h q6; x q0; x q1; x q2; x q3; x q4; x q5; x q6; h q0; h q1; h q2; h q3; h q4; h q5; h q6; }
gate gate_Q_134450612168576 q0,q1,q2,q3,q4,q5,q6,q7 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7; }
gate gate_Q_134450612165936 q0,q1,q2,q3,q4,q5,q6,q7 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7; }
gate gate_Q_134450611871024 q0,q1,q2,q3,q4,q5,q6,q7 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7; }
gate gate_Q_134450610563520 q0,q1,q2,q3,q4,q5,q6,q7 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7; }
gate gate_Q_134450610566112 q0,q1,q2,q3,q4,q5,q6,q7 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7; }
gate gate_Q_134450610566736 q0,q1,q2,q3,q4,q5,q6,q7 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7; }
gate gate_Q_134450613718288 q0,q1,q2,q3,q4,q5,q6,q7 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7; }
gate gate_Q_134450610511392 q0,q1,q2,q3,q4,q5,q6,q7 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7; }
qreg q[7];
qreg flag[1];
creg meas[8];
h q[0];
h q[1];
h q[2];
h q[3];
h q[4];
h q[5];
h q[6];
x flag[0];
gate_Q_134450612168576 q[0],q[1],q[2],q[3],q[4],q[5],q[6],flag[0];
gate_Q_134450612165936 q[0],q[1],q[2],q[3],q[4],q[5],q[6],flag[0];
gate_Q_134450611871024 q[0],q[1],q[2],q[3],q[4],q[5],q[6],flag[0];
gate_Q_134450610563520 q[0],q[1],q[2],q[3],q[4],q[5],q[6],flag[0];
gate_Q_134450610566112 q[0],q[1],q[2],q[3],q[4],q[5],q[6],flag[0];
gate_Q_134450610566736 q[0],q[1],q[2],q[3],q[4],q[5],q[6],flag[0];
gate_Q_134450613718288 q[0],q[1],q[2],q[3],q[4],q[5],q[6],flag[0];
gate_Q_134450610511392 q[0],q[1],q[2],q[3],q[4],q[5],q[6],flag[0];
barrier q[0],q[1],q[2],q[3],q[4],q[5],q[6],flag[0];
measure q[0] -> meas[0];
measure q[1] -> meas[1];
measure q[2] -> meas[2];
measure q[3] -> meas[3];
measure q[4] -> meas[4];
measure q[5] -> meas[5];
measure q[6] -> meas[6];
measure flag[0] -> meas[7];