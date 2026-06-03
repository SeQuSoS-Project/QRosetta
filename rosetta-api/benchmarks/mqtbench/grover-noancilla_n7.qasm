OPENQASM 2.0;
include "qelib1.inc";
gate mcx_vchain q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary q0 { u(0,-pi/8,-pi/8) q0; }
gate unitary_134450612345680 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450613186640 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450612834416 q0 { u(0,-pi/16,-pi/16) q0; }
gate unitary_134450612678640 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate unitary_134450614393104 q0 { u(0,-pi/16,-pi/16) q0; }
gate unitary_134450613190048 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate unitary_134450611111648 q0 { u(0,-pi/32,-pi/32) q0; }
gate unitary_134450614393584 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate unitary_134450614388544 q0 { u(0,-pi/32,-pi/32) q0; }
gate unitary_134450611719104 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate unitary_134450611723424 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450611729664 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate unitary_134450614393440 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450611726400 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate unitary_134450611728944 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450611732112 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate unitary_134450611730576 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450611720832 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcphase(param0) q0,q1,q2,q3,q4,q5,q6 { mcx_vchain q0,q1,q2,q6,q3; unitary q6; mcx_vchain q3,q4,q5,q6,q2; unitary_134450612345680 q6; mcx_vchain q0,q1,q2,q6,q3; unitary q6; mcx_vchain q3,q4,q5,q6,q2; unitary_134450613186640 q6; mcx_vchain q0,q1,q2,q5,q3; unitary_134450612834416 q5; ccx q3,q4,q5; unitary_134450612678640 q5; mcx_vchain q0,q1,q2,q5,q3; unitary_134450614393104 q5; ccx q3,q4,q5; unitary_134450613190048 q5; ccx q0,q1,q4; unitary_134450611111648 q4; ccx q2,q3,q4; unitary_134450614393584 q4; ccx q0,q1,q4; unitary_134450614388544 q4; ccx q2,q3,q4; unitary_134450611719104 q4; ccx q0,q1,q3; unitary_134450611723424 q3; cx q2,q3; unitary_134450611729664 q3; ccx q0,q1,q3; unitary_134450614393440 q3; cx q2,q3; unitary_134450611726400 q3; cx q0,q2; unitary_134450611728944 q2; cx q1,q2; unitary_134450611732112 q2; cx q0,q2; unitary_134450611730576 q2; cx q1,q2; unitary_134450611720832 q2; crz(pi/32) q0,q1; p(pi/64) q0; }
gate unitary_134450611417312 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450611416256 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450611420048 q0 { u(0,-pi/16,-pi/16) q0; }
gate unitary_134450611727168 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate unitary_134450611420192 q0 { u(0,-pi/16,-pi/16) q0; }
gate unitary_134450611406896 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate unitary_134450611418944 q0 { u(0,-pi/32,-pi/32) q0; }
gate unitary_134450611419952 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate unitary_134450611415392 q0 { u(0,-pi/32,-pi/32) q0; }
gate unitary_134450611413712 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate unitary_134450611718768 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450611412944 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate unitary_134450611411072 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450611408576 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcphase_134450611723040(param0) q0,q1,q2,q3,q4,q5 { mcx_vchain q0,q1,q2,q5,q3; unitary q5; ccx q3,q4,q5; unitary_134450611417312 q5; mcx_vchain q0,q1,q2,q5,q3; unitary q5; ccx q3,q4,q5; unitary_134450611416256 q5; ccx q0,q1,q4; unitary_134450611420048 q4; ccx q2,q3,q4; unitary_134450611727168 q4; ccx q0,q1,q4; unitary_134450611420192 q4; ccx q2,q3,q4; unitary_134450611406896 q4; ccx q0,q1,q3; unitary_134450611418944 q3; cx q2,q3; unitary_134450611419952 q3; ccx q0,q1,q3; unitary_134450611415392 q3; cx q2,q3; unitary_134450611413712 q3; cx q0,q2; unitary_134450611718768 q2; cx q1,q2; unitary_134450611412944 q2; cx q0,q2; unitary_134450611411072 q2; cx q1,q2; unitary_134450611408576 q2; crz(pi/16) q0,q1; p(pi/32) q0; }
gate mcx q0,q1,q2,q3,q4,q5 { h q5; mcphase_134450611723040(pi) q0,q1,q2,q3,q4,q5; h q5; }
gate gate_Q q0,q1,q2,q3,q4,q5,q6 { mcphase(pi) q0,q1,q2,q3,q4,q5,q6; h q5; h q4; h q3; h q2; h q1; h q0; x q0; x q1; x q2; x q3; x q4; x q5; h q5; mcx q0,q1,q2,q3,q4,q5; h q5; x q0; x q1; x q2; x q3; x q4; x q5; h q0; h q1; h q2; h q3; h q4; h q5; }
gate gate_Q_134450614397856 q0,q1,q2,q3,q4,q5,q6 { gate_Q q0,q1,q2,q3,q4,q5,q6; }
gate gate_Q_134450613174448 q0,q1,q2,q3,q4,q5,q6 { gate_Q q0,q1,q2,q3,q4,q5,q6; }
gate gate_Q_134450611405072 q0,q1,q2,q3,q4,q5,q6 { gate_Q q0,q1,q2,q3,q4,q5,q6; }
gate gate_Q_134450614397520 q0,q1,q2,q3,q4,q5,q6 { gate_Q q0,q1,q2,q3,q4,q5,q6; }
gate gate_Q_134450611119952 q0,q1,q2,q3,q4,q5,q6 { gate_Q q0,q1,q2,q3,q4,q5,q6; }
gate gate_Q_134450612321552 q0,q1,q2,q3,q4,q5,q6 { gate_Q q0,q1,q2,q3,q4,q5,q6; }
qreg q[6];
qreg flag[1];
creg meas[7];
h q[0];
h q[1];
h q[2];
h q[3];
h q[4];
h q[5];
x flag[0];
gate_Q_134450614397856 q[0],q[1],q[2],q[3],q[4],q[5],flag[0];
gate_Q_134450613174448 q[0],q[1],q[2],q[3],q[4],q[5],flag[0];
gate_Q_134450611405072 q[0],q[1],q[2],q[3],q[4],q[5],flag[0];
gate_Q_134450614397520 q[0],q[1],q[2],q[3],q[4],q[5],flag[0];
gate_Q_134450611119952 q[0],q[1],q[2],q[3],q[4],q[5],flag[0];
gate_Q_134450612321552 q[0],q[1],q[2],q[3],q[4],q[5],flag[0];
barrier q[0],q[1],q[2],q[3],q[4],q[5],flag[0];
measure q[0] -> meas[0];
measure q[1] -> meas[1];
measure q[2] -> meas[2];
measure q[3] -> meas[3];
measure q[4] -> meas[4];
measure q[5] -> meas[5];
measure flag[0] -> meas[6];