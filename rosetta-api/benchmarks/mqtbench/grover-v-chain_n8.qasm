OPENQASM 2.0;
include "qelib1.inc";
gate mcx_vchain q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary q0 { u(0,-pi/8,-pi/8) q0; }
gate mcx_vchain_134450496632976 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450495580224 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450496620160 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450494567392 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450493993424 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450495578256 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450493987760 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450497635248 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450493982528 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450496267680 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450493994288 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450492716096 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450493213584 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450496268256 q0 { u(0,-pi/32,-pi/32) q0; }
gate unitary_134450498029952 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450493224240 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450499023744 q0 { u(0,-pi/32,-pi/32) q0; }
gate unitary_134450551981504 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate unitary_134450551989568 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450493223328 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate unitary_134450566635904 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450498037104 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate unitary_134450498710480 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450499756032 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate unitary_134450499754496 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450499453824 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate unitary_134450499459680 q0 { u(0,-pi/256,-pi/256) q0; }
gate unitary_134450499762608 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate unitary_134450551980976 q0 { u(0,-pi/256,-pi/256) q0; }
gate unitary_134450500865968 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcphase(param0) q0,q1,q2,q3,q4,q5,q6,q7 { mcx_vchain q0,q1,q2,q3,q7,q4,q5; unitary q7; mcx_vchain_134450496632976 q4,q5,q6,q7,q3; unitary_134450495580224 q7; mcx_vchain q0,q1,q2,q3,q7,q4,q5; unitary q7; mcx_vchain_134450496620160 q4,q5,q6,q7,q3; unitary_134450494567392 q7; mcx_vchain_134450493993424 q0,q1,q2,q6,q3; unitary_134450495578256 q6; mcx_vchain_134450493987760 q3,q4,q5,q6,q2; unitary_134450497635248 q6; mcx_vchain_134450493982528 q0,q1,q2,q6,q3; unitary_134450496267680 q6; mcx_vchain_134450493994288 q3,q4,q5,q6,q2; unitary_134450492716096 q6; mcx_vchain_134450493213584 q0,q1,q2,q5,q3; unitary_134450496268256 q5; ccx q3,q4,q5; unitary_134450498029952 q5; mcx_vchain_134450493224240 q0,q1,q2,q5,q3; unitary_134450499023744 q5; ccx q3,q4,q5; unitary_134450551981504 q5; ccx q0,q1,q4; unitary_134450551989568 q4; ccx q2,q3,q4; unitary_134450493223328 q4; ccx q0,q1,q4; unitary_134450566635904 q4; ccx q2,q3,q4; unitary_134450498037104 q4; ccx q0,q1,q3; unitary_134450498710480 q3; cx q2,q3; unitary_134450499756032 q3; ccx q0,q1,q3; unitary_134450499754496 q3; cx q2,q3; unitary_134450499453824 q3; cx q0,q2; unitary_134450499459680 q2; cx q1,q2; unitary_134450499762608 q2; cx q0,q2; unitary_134450551980976 q2; cx q1,q2; unitary_134450500865968 q2; crz(pi/64) q0,q1; p(pi/128) q0; }
gate mcx_vchain_134450504229488 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { rccx q0,q1,q7; rccx q2,q7,q8; rccx q3,q8,q9; rccx q4,q9,q10; ccx q5,q10,q6; rccx q4,q9,q10; rccx q3,q8,q9; rccx q2,q7,q8; rccx q0,q1,q7; }
gate gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { mcphase(pi) q0,q1,q2,q3,q4,q5,q6,q7; h q6; h q5; h q4; h q3; h q2; h q1; h q0; x q0; x q1; x q2; x q3; x q4; x q5; x q6; h q6; mcx_vchain_134450504229488 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; h q6; x q0; x q1; x q2; x q3; x q4; x q5; x q6; h q0; h q1; h q2; h q3; h q4; h q5; h q6; }
gate gate_Q_134450549883056 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450549898848 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450549893712 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450501941536 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450501555296 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450496038304 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450500503888 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450494563648 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
qreg q[10];
qreg flag[1];
creg meas[11];
h q[0];
h q[1];
h q[2];
h q[3];
h q[4];
h q[5];
h q[6];
x q[7];
gate_Q_134450549883056 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450549898848 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450549893712 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450501941536 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450501555296 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450496038304 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450500503888 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450494563648 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
barrier q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
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
measure flag[0] -> meas[10];