OPENQASM 2.0;
include "qelib1.inc";
gate mcx_vchain q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; ccx q5,q10,q6; h q10; t q10; cx q4,q10; tdg q10; cx q9,q10; h q9; t q9; cx q3,q9; tdg q9; cx q8,q9; h q8; t q8; cx q2,q8; tdg q8; cx q7,q8; h q7; t q7; cx q0,q7; tdg q7; cx q1,q7; t q7; cx q0,q7; tdg q7; h q7; cx q7,q8; t q8; cx q2,q8; tdg q8; h q8; cx q8,q9; t q9; cx q3,q9; tdg q9; h q9; cx q9,q10; t q10; cx q4,q10; tdg q10; h q10; }
gate unitary q0 { u(0,-pi/8,-pi/8) q0; }
gate unitary_134450610988832 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450572756800 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450610860448 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450611192896 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450610862848 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate unitary_134450610863088 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450611192704 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450610725344 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450611193280 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450610721792 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450573611744 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450610724816 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450572764816 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450570844960 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450611201824 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450610731248 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450610993344 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450610727264 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450610994688 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450610724144 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450610994928 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450610635408 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450610995168 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450610649136 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450610990416 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450610726736 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450610990272 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450610649088 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450610989696 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450610638432 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450610989456 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450610640016 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450610988880 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450610644624 q0 { u(0,-pi/256,-pi/256) q0; }
gate mcx_vchain_134450610986816 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610644864 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcx_vchain_134450610983408 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450610637760 q0 { u(0,-pi/256,-pi/256) q0; }
gate mcx_vchain_134450610988400 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610555840 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcx_vchain_134450610993632 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610561072 q0 { u(0,-pi/512,-pi/512) q0; }
gate mcx_vchain_134450610986144 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610646496 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate mcx_vchain_134450610990368 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610561216 q0 { u(0,-pi/512,-pi/512) q0; }
gate mcx_vchain_134450610992816 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610566304 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate mcx_vchain_134450610981344 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610566448 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate unitary_134450610559872 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate mcx_vchain_134450610989936 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450610636752 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate unitary_134450610564864 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate unitary_134450610561888 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate unitary_134450610553632 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate unitary_134450610513504 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate unitary_134450610507360 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate unitary_134450610504240 q0 { u(0,-pi/4096,-pi/4096) q0; }
gate unitary_134450573289008 q0 { u(0,-3.14082566319585,3.142359643983736) q0; }
gate unitary_134450610518352 q0 { u(0,-pi/4096,-pi/4096) q0; }
gate unitary_134450610510288 q0 { u(0,-3.14082566319585,3.142359643983736) q0; }
gate unitary_134450610509376 q0 { u(0,-pi/8192,-pi/8192) q0; }
gate unitary_134450610519648 q0 { u(0,-3.141209158392822,3.1419761487867643) q0; }
gate unitary_134450610512400 q0 { u(0,-pi/8192,-pi/8192) q0; }
gate unitary_134450610511776 q0 { u(0,-3.141209158392822,3.1419761487867643) q0; }
gate mcphase(param0) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { mcx_vchain q0,q1,q2,q3,q4,q5,q12,q6,q7,q8,q9; unitary q12; mcx_vchain q6,q7,q8,q9,q10,q11,q12,q2,q3,q4,q5; unitary_134450610988832 q12; mcx_vchain q0,q1,q2,q3,q4,q5,q12,q6,q7,q8,q9; unitary q12; mcx_vchain q6,q7,q8,q9,q10,q11,q12,q2,q3,q4,q5; unitary_134450572756800 q12; mcx_vchain q0,q1,q2,q3,q4,q5,q11,q6,q7,q8,q9; unitary_134450610860448 q11; mcx_vchain_134450611192896 q6,q7,q8,q9,q10,q11,q3,q4,q5; unitary_134450610862848 q11; mcx_vchain q0,q1,q2,q3,q4,q5,q11,q6,q7,q8,q9; unitary_134450610863088 q11; mcx_vchain_134450611192704 q6,q7,q8,q9,q10,q11,q3,q4,q5; unitary_134450610725344 q11; mcx_vchain_134450611193280 q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary_134450610721792 q10; mcx_vchain_134450573611744 q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450610724816 q10; mcx_vchain_134450572764816 q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary_134450570844960 q10; mcx_vchain_134450611201824 q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450610731248 q10; mcx_vchain_134450610993344 q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450610727264 q9; mcx_vchain_134450610994688 q5,q6,q7,q8,q9,q3,q4; unitary_134450610724144 q9; mcx_vchain_134450610994928 q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450610635408 q9; mcx_vchain_134450610995168 q5,q6,q7,q8,q9,q3,q4; unitary_134450610649136 q9; mcx_vchain_134450610990416 q0,q1,q2,q3,q8,q4,q5; unitary_134450610726736 q8; mcx_vchain_134450610990272 q4,q5,q6,q7,q8,q2,q3; unitary_134450610649088 q8; mcx_vchain_134450610989696 q0,q1,q2,q3,q8,q4,q5; unitary_134450610638432 q8; mcx_vchain_134450610989456 q4,q5,q6,q7,q8,q2,q3; unitary_134450610640016 q8; mcx_vchain_134450610988880 q0,q1,q2,q3,q7,q4,q5; unitary_134450610644624 q7; mcx_vchain_134450610986816 q4,q5,q6,q7,q3; unitary_134450610644864 q7; mcx_vchain_134450610983408 q0,q1,q2,q3,q7,q4,q5; unitary_134450610637760 q7; mcx_vchain_134450610988400 q4,q5,q6,q7,q3; unitary_134450610555840 q7; mcx_vchain_134450610993632 q0,q1,q2,q6,q3; unitary_134450610561072 q6; mcx_vchain_134450610986144 q3,q4,q5,q6,q2; unitary_134450610646496 q6; mcx_vchain_134450610990368 q0,q1,q2,q6,q3; unitary_134450610561216 q6; mcx_vchain_134450610992816 q3,q4,q5,q6,q2; unitary_134450610566304 q6; mcx_vchain_134450610981344 q0,q1,q2,q5,q3; unitary_134450610566448 q5; ccx q3,q4,q5; unitary_134450610559872 q5; mcx_vchain_134450610989936 q0,q1,q2,q5,q3; unitary_134450610636752 q5; ccx q3,q4,q5; unitary_134450610564864 q5; ccx q0,q1,q4; unitary_134450610561888 q4; ccx q2,q3,q4; unitary_134450610553632 q4; ccx q0,q1,q4; unitary_134450610513504 q4; ccx q2,q3,q4; unitary_134450610507360 q4; ccx q0,q1,q3; unitary_134450610504240 q3; cx q2,q3; unitary_134450573289008 q3; ccx q0,q1,q3; unitary_134450610518352 q3; cx q2,q3; unitary_134450610510288 q3; cx q0,q2; unitary_134450610509376 q2; cx q1,q2; unitary_134450610519648 q2; cx q0,q2; unitary_134450610512400 q2; cx q1,q2; unitary_134450610511776 q2; crz(pi/2048) q0,q1; p(pi/4096) q0; }
gate mcx_vchain_134450610387232 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450612347024 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450610373024 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450612349040 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450610388240 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450610385936 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450610376768 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450610382720 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450610387040 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450610510096 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450610375136 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450610384880 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450610379264 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450610635168 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450610377056 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450610388576 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450610379552 q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary_134450573294624 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450610382672 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450610981728 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450610380896 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450611195872 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450610381184 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450611193328 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450610374032 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450611193760 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450610388048 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450612341216 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450610383872 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450612341792 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450610383920 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450612353072 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450610384016 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450612351776 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450610383584 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450612350672 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450610383344 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450612353456 q0 { u(0,-pi/256,-pi/256) q0; }
gate mcx_vchain_134450610388096 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450612318528 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcx_vchain_134450610388432 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450612310752 q0 { u(0,-pi/256,-pi/256) q0; }
gate mcx_vchain_134450610378640 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450612340208 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcx_vchain_134450610384592 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450612307440 q0 { u(0,-pi/512,-pi/512) q0; }
gate unitary_134450612319776 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate mcx_vchain_134450610378736 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450612306000 q0 { u(0,-pi/512,-pi/512) q0; }
gate unitary_134450612314208 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate unitary_134450612317088 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate unitary_134450612318432 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate unitary_134450612320928 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate unitary_134450612309168 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate unitary_134450627729680 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate unitary_134450612170352 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate unitary_134450612167568 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate unitary_134450612162912 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate unitary_134450612318336 q0 { u(0,-pi/4096,-pi/4096) q0; }
gate unitary_134450612169536 q0 { u(0,-3.14082566319585,3.142359643983736) q0; }
gate unitary_134450612166128 q0 { u(0,-pi/4096,-pi/4096) q0; }
gate unitary_134450612173472 q0 { u(0,-3.14082566319585,3.142359643983736) q0; }
gate mcphase_134450610517344(param0) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { mcx_vchain q0,q1,q2,q3,q4,q5,q11,q6,q7,q8,q9; unitary q11; mcx_vchain_134450610387232 q6,q7,q8,q9,q10,q11,q3,q4,q5; unitary_134450612347024 q11; mcx_vchain q0,q1,q2,q3,q4,q5,q11,q6,q7,q8,q9; unitary q11; mcx_vchain_134450610373024 q6,q7,q8,q9,q10,q11,q3,q4,q5; unitary_134450612349040 q11; mcx_vchain_134450610388240 q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary_134450610385936 q10; mcx_vchain_134450610376768 q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450610382720 q10; mcx_vchain_134450610387040 q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary_134450610510096 q10; mcx_vchain_134450610375136 q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450610384880 q10; mcx_vchain_134450610379264 q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450610635168 q9; mcx_vchain_134450610377056 q5,q6,q7,q8,q9,q3,q4; unitary_134450610388576 q9; mcx_vchain_134450610379552 q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450573294624 q9; mcx_vchain_134450610382672 q5,q6,q7,q8,q9,q3,q4; unitary_134450610981728 q9; mcx_vchain_134450610380896 q0,q1,q2,q3,q8,q4,q5; unitary_134450611195872 q8; mcx_vchain_134450610381184 q4,q5,q6,q7,q8,q2,q3; unitary_134450611193328 q8; mcx_vchain_134450610374032 q0,q1,q2,q3,q8,q4,q5; unitary_134450611193760 q8; mcx_vchain_134450610388048 q4,q5,q6,q7,q8,q2,q3; unitary_134450612341216 q8; mcx_vchain_134450610383872 q0,q1,q2,q3,q7,q4,q5; unitary_134450612341792 q7; mcx_vchain_134450610383920 q4,q5,q6,q7,q3; unitary_134450612353072 q7; mcx_vchain_134450610384016 q0,q1,q2,q3,q7,q4,q5; unitary_134450612351776 q7; mcx_vchain_134450610383584 q4,q5,q6,q7,q3; unitary_134450612350672 q7; mcx_vchain_134450610383344 q0,q1,q2,q6,q3; unitary_134450612353456 q6; mcx_vchain_134450610388096 q3,q4,q5,q6,q2; unitary_134450612318528 q6; mcx_vchain_134450610388432 q0,q1,q2,q6,q3; unitary_134450612310752 q6; mcx_vchain_134450610378640 q3,q4,q5,q6,q2; unitary_134450612340208 q6; mcx_vchain_134450610384592 q0,q1,q2,q5,q3; unitary_134450612307440 q5; ccx q3,q4,q5; unitary_134450612319776 q5; mcx_vchain_134450610378736 q0,q1,q2,q5,q3; unitary_134450612306000 q5; ccx q3,q4,q5; unitary_134450612314208 q5; ccx q0,q1,q4; unitary_134450612317088 q4; ccx q2,q3,q4; unitary_134450612318432 q4; ccx q0,q1,q4; unitary_134450612320928 q4; ccx q2,q3,q4; unitary_134450612309168 q4; ccx q0,q1,q3; unitary_134450627729680 q3; cx q2,q3; unitary_134450612170352 q3; ccx q0,q1,q3; unitary_134450612167568 q3; cx q2,q3; unitary_134450612162912 q3; cx q0,q2; unitary_134450612318336 q2; cx q1,q2; unitary_134450612169536 q2; cx q0,q2; unitary_134450612166128 q2; cx q1,q2; unitary_134450612173472 q2; crz(pi/1024) q0,q1; p(pi/2048) q0; }
gate mcx q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11 { h q11; mcphase_134450610517344(pi) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; h q11; }
gate gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { mcphase(pi) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; h q11; h q10; h q9; h q8; h q7; h q6; h q5; h q4; h q3; h q2; h q1; h q0; x q0; x q1; x q2; x q3; x q4; x q5; x q6; x q7; x q8; x q9; x q10; x q11; h q11; mcx q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11; h q11; x q0; x q1; x q2; x q3; x q4; x q5; x q6; x q7; x q8; x q9; x q10; x q11; h q0; h q1; h q2; h q3; h q4; h q5; h q6; h q7; h q8; h q9; h q10; h q11; }
gate gate_Q_134450611199088 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450573293952 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450610508848 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450610993776 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611200288 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450612173136 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450612161664 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450612159888 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450612035536 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450612039232 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450570853168 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450612040096 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450612350768 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450610854544 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450610560640 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611919264 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611916576 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611923008 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611918496 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611919456 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611872608 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611873424 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611863872 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611871504 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611864352 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611720352 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611718480 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611726640 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450612310464 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611534592 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450610372880 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611721024 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611873328 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450610728752 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611526096 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611529024 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611523024 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611420528 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611420912 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611419664 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611409824 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450611920464 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450613322864 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450613329824 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450613332608 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450613332272 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450612167760 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450613181024 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450613179920 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
gate gate_Q_134450613188944 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10,q11,q12; }
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
h q[8];
h q[9];
h q[10];
h q[11];
x flag[0];
gate_Q_134450611199088 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450573293952 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450610508848 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450610993776 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611200288 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450612173136 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450612161664 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450612159888 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450612035536 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450612039232 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450570853168 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450612040096 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450612350768 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450610854544 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450610560640 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611919264 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611916576 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611923008 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611918496 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611919456 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611872608 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611873424 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611863872 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611871504 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611864352 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611720352 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611718480 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611726640 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450612310464 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611534592 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450610372880 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611721024 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611873328 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450610728752 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611526096 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611529024 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611523024 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611420528 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611420912 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611419664 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611409824 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450611920464 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450613322864 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450613329824 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450613332608 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450613332272 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450612167760 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450613181024 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450613179920 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
gate_Q_134450613188944 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],q[10],q[11],flag[0];
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