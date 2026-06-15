OPENQASM 2.0;
include "qelib1.inc";
gate mcx_vchain q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary q0 { u(0,-pi/8,-pi/8) q0; }
gate unitary_134450612724528 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450612723904 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450612721696 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450612726688 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610724672 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate unitary_134450610728080 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450612729088 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610727840 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450610516768 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610727360 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450610514080 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610719248 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450641904144 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610720688 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450613727840 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610722512 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450612717376 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610723280 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450610720064 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450612718480 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610730000 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450610731200 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate unitary_134450610732736 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450610980816 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate unitary_134450610732208 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450610722656 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate unitary_134450610981008 q0 { u(0,-pi/256,-pi/256) q0; }
gate unitary_134450610992960 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate unitary_134450610992144 q0 { u(0,-pi/256,-pi/256) q0; }
gate unitary_134450610990656 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate unitary_134450610989600 q0 { u(0,-pi/512,-pi/512) q0; }
gate unitary_134450610989072 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate unitary_134450610988352 q0 { u(0,-pi/512,-pi/512) q0; }
gate unitary_134450610990464 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate mcphase(param0) q0,q1,q2,q3,q4,q5,q6,q7,q8 { mcx_vchain q0,q1,q2,q3,q8,q4,q5; unitary q8; mcx_vchain q4,q5,q6,q7,q8,q2,q3; unitary_134450612724528 q8; mcx_vchain q0,q1,q2,q3,q8,q4,q5; unitary q8; mcx_vchain q4,q5,q6,q7,q8,q2,q3; unitary_134450612723904 q8; mcx_vchain q0,q1,q2,q3,q7,q4,q5; unitary_134450612721696 q7; mcx_vchain_134450612726688 q4,q5,q6,q7,q3; unitary_134450610724672 q7; mcx_vchain q0,q1,q2,q3,q7,q4,q5; unitary_134450610728080 q7; mcx_vchain_134450612729088 q4,q5,q6,q7,q3; unitary_134450610727840 q7; mcx_vchain_134450610516768 q0,q1,q2,q6,q3; unitary_134450610727360 q6; mcx_vchain_134450610514080 q3,q4,q5,q6,q2; unitary_134450610719248 q6; mcx_vchain_134450641904144 q0,q1,q2,q6,q3; unitary_134450610720688 q6; mcx_vchain_134450613727840 q3,q4,q5,q6,q2; unitary_134450610722512 q6; mcx_vchain_134450612717376 q0,q1,q2,q5,q3; unitary_134450610723280 q5; ccx q3,q4,q5; unitary_134450610720064 q5; mcx_vchain_134450612718480 q0,q1,q2,q5,q3; unitary_134450610730000 q5; ccx q3,q4,q5; unitary_134450610731200 q5; ccx q0,q1,q4; unitary_134450610732736 q4; ccx q2,q3,q4; unitary_134450610980816 q4; ccx q0,q1,q4; unitary_134450610732208 q4; ccx q2,q3,q4; unitary_134450610722656 q4; ccx q0,q1,q3; unitary_134450610981008 q3; cx q2,q3; unitary_134450610992960 q3; ccx q0,q1,q3; unitary_134450610992144 q3; cx q2,q3; unitary_134450610990656 q3; cx q0,q2; unitary_134450610989600 q2; cx q1,q2; unitary_134450610989072 q2; cx q0,q2; unitary_134450610988352 q2; cx q1,q2; unitary_134450610990464 q2; crz(pi/128) q0,q1; p(pi/256) q0; }
gate mcx_vchain_134450610985232 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610645776 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450610984608 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610642896 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450610983504 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610643376 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450610983888 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610989168 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450610983792 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610718192 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450610983696 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450612731392 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450610638000 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450612719872 q0 { u(0,-pi/32,-pi/32) q0; }
gate unitary_134450613186976 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450610642512 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450612716848 q0 { u(0,-pi/32,-pi/32) q0; }
gate unitary_134450610989840 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate unitary_134450612029440 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450611875296 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate unitary_134450610512880 q0 { u(0,-pi/64,-pi/64) q0; }
gate unitary_134450610516576 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate unitary_134450613718960 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450610511056 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate unitary_134450611730768 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450613728464 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate unitary_134450613729136 q0 { u(0,-pi/256,-pi/256) q0; }
gate unitary_134450610644336 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate unitary_134450610645584 q0 { u(0,-pi/256,-pi/256) q0; }
gate unitary_134450610642992 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcphase_134450610987872(param0) q0,q1,q2,q3,q4,q5,q6,q7 { mcx_vchain q0,q1,q2,q3,q7,q4,q5; unitary q7; mcx_vchain_134450610985232 q4,q5,q6,q7,q3; unitary_134450610645776 q7; mcx_vchain q0,q1,q2,q3,q7,q4,q5; unitary q7; mcx_vchain_134450610984608 q4,q5,q6,q7,q3; unitary_134450610642896 q7; mcx_vchain_134450610983504 q0,q1,q2,q6,q3; unitary_134450610643376 q6; mcx_vchain_134450610983888 q3,q4,q5,q6,q2; unitary_134450610989168 q6; mcx_vchain_134450610983792 q0,q1,q2,q6,q3; unitary_134450610718192 q6; mcx_vchain_134450610983696 q3,q4,q5,q6,q2; unitary_134450612731392 q6; mcx_vchain_134450610638000 q0,q1,q2,q5,q3; unitary_134450612719872 q5; ccx q3,q4,q5; unitary_134450613186976 q5; mcx_vchain_134450610642512 q0,q1,q2,q5,q3; unitary_134450612716848 q5; ccx q3,q4,q5; unitary_134450610989840 q5; ccx q0,q1,q4; unitary_134450612029440 q4; ccx q2,q3,q4; unitary_134450611875296 q4; ccx q0,q1,q4; unitary_134450610512880 q4; ccx q2,q3,q4; unitary_134450610516576 q4; ccx q0,q1,q3; unitary_134450613718960 q3; cx q2,q3; unitary_134450610511056 q3; ccx q0,q1,q3; unitary_134450611730768 q3; cx q2,q3; unitary_134450613728464 q3; cx q0,q2; unitary_134450613729136 q2; cx q1,q2; unitary_134450610644336 q2; cx q0,q2; unitary_134450610645584 q2; cx q1,q2; unitary_134450610642992 q2; crz(pi/64) q0,q1; p(pi/128) q0; }
gate mcx q0,q1,q2,q3,q4,q5,q6,q7 { h q7; mcphase_134450610987872(pi) q0,q1,q2,q3,q4,q5,q6,q7; h q7; }
gate gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8 { mcphase(pi) q0,q1,q2,q3,q4,q5,q6,q7,q8; h q7; h q6; h q5; h q4; h q3; h q2; h q1; h q0; x q0; x q1; x q2; x q3; x q4; x q5; x q6; x q7; h q7; mcx q0,q1,q2,q3,q4,q5,q6,q7; h q7; x q0; x q1; x q2; x q3; x q4; x q5; x q6; x q7; h q0; h q1; h q2; h q3; h q4; h q5; h q6; h q7; }
gate gate_Q_134450610508224 q0,q1,q2,q3,q4,q5,q6,q7,q8 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8; }
gate gate_Q_134450612730000 q0,q1,q2,q3,q4,q5,q6,q7,q8 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8; }
gate gate_Q_134450610988112 q0,q1,q2,q3,q4,q5,q6,q7,q8 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8; }
gate gate_Q_134450613717088 q0,q1,q2,q3,q4,q5,q6,q7,q8 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8; }
gate gate_Q_134450611868288 q0,q1,q2,q3,q4,q5,q6,q7,q8 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8; }
gate gate_Q_134450610638288 q0,q1,q2,q3,q4,q5,q6,q7,q8 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8; }
gate gate_Q_134450610509088 q0,q1,q2,q3,q4,q5,q6,q7,q8 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8; }
gate gate_Q_134450610639152 q0,q1,q2,q3,q4,q5,q6,q7,q8 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8; }
gate gate_Q_134450610649040 q0,q1,q2,q3,q4,q5,q6,q7,q8 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8; }
gate gate_Q_134450610648128 q0,q1,q2,q3,q4,q5,q6,q7,q8 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8; }
gate gate_Q_134450610651056 q0,q1,q2,q3,q4,q5,q6,q7,q8 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8; }
gate gate_Q_134450610856224 q0,q1,q2,q3,q4,q5,q6,q7,q8 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8; }
qreg q[8];
qreg flag[1];
creg meas[9];
h q[0];
h q[1];
h q[2];
h q[3];
h q[4];
h q[5];
h q[6];
h q[7];
x flag[0];
gate_Q_134450610508224 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],flag[0];
gate_Q_134450612730000 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],flag[0];
gate_Q_134450610988112 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],flag[0];
gate_Q_134450613717088 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],flag[0];
gate_Q_134450611868288 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],flag[0];
gate_Q_134450610638288 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],flag[0];
gate_Q_134450610509088 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],flag[0];
gate_Q_134450610639152 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],flag[0];
gate_Q_134450610649040 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],flag[0];
gate_Q_134450610648128 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],flag[0];
gate_Q_134450610651056 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],flag[0];
gate_Q_134450610856224 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],flag[0];
barrier q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],flag[0];
measure q[0] -> meas[0];
measure q[1] -> meas[1];
measure q[2] -> meas[2];
measure q[3] -> meas[3];
measure q[4] -> meas[4];
measure q[5] -> meas[5];
measure q[6] -> meas[6];
measure q[7] -> meas[7];
measure flag[0] -> meas[8];