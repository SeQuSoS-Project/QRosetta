OPENQASM 2.0;
include "qelib1.inc";
gate mcx_vchain q0,q1,q2,q3,q4,q5,q6,q7,q8 { ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; ccx q4,q8,q5; h q8; t q8; cx q3,q8; tdg q8; cx q7,q8; h q7; t q7; cx q2,q7; tdg q7; cx q6,q7; h q6; t q6; cx q0,q6; tdg q6; cx q1,q6; t q6; cx q0,q6; tdg q6; h q6; cx q6,q7; t q7; cx q2,q7; tdg q7; h q7; cx q7,q8; t q8; cx q3,q8; tdg q8; h q8; }
gate unitary q0 { u(0,-pi/8,-pi/8) q0; }
gate unitary_134450572756896 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450574319808 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate unitary_134450572758720 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450574715136 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450572758864 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate unitary_134450572763520 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450574715280 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450572755216 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450574717776 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450574716144 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450574717392 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450574711680 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450574717488 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450610149456 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450574717584 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450574719312 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450574714512 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450574043728 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450574716720 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450574716192 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450574716048 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450612722416 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450574716000 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450573824784 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450574719696 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450572755840 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450574719408 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450572764336 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450574718784 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450574039456 q0 { u(0,-pi/128,-pi/128) q0; }
gate mcx_vchain_134450574719504 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450572764960 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450572755168 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450572766400 q0 { u(0,-pi/256,-pi/256) q0; }
gate unitary_134450572767312 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate mcx_vchain_134450574720944 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450572768560 q0 { u(0,-pi/256,-pi/256) q0; }
gate unitary_134450572769424 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate unitary_134450574036720 q0 { u(0,-pi/512,-pi/512) q0; }
gate unitary_134450572766544 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate unitary_134450572768128 q0 { u(0,-pi/512,-pi/512) q0; }
gate unitary_134450572769712 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate unitary_134450572770096 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate unitary_134450572770912 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate unitary_134450572918960 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate unitary_134450572771104 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate unitary_134450572758096 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate unitary_134450572920496 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate unitary_134450572920160 q0 { u(0,-pi/2048,-pi/2048) q0; }
gate unitary_134450572921072 q0 { u(0,-3.1400586728019073,3.143126634377679) q0; }
gate mcphase(param0) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { mcx_vchain q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary q10; mcx_vchain q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450572756896 q10; mcx_vchain q0,q1,q2,q3,q4,q10,q5,q6,q7; unitary q10; mcx_vchain q5,q6,q7,q8,q9,q10,q2,q3,q4; unitary_134450574319808 q10; mcx_vchain q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450572758720 q9; mcx_vchain_134450574715136 q5,q6,q7,q8,q9,q3,q4; unitary_134450572758864 q9; mcx_vchain q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary_134450572763520 q9; mcx_vchain_134450574715280 q5,q6,q7,q8,q9,q3,q4; unitary_134450572755216 q9; mcx_vchain_134450574717776 q0,q1,q2,q3,q8,q4,q5; unitary_134450574716144 q8; mcx_vchain_134450574717392 q4,q5,q6,q7,q8,q2,q3; unitary_134450574711680 q8; mcx_vchain_134450574717488 q0,q1,q2,q3,q8,q4,q5; unitary_134450610149456 q8; mcx_vchain_134450574717584 q4,q5,q6,q7,q8,q2,q3; unitary_134450574719312 q8; mcx_vchain_134450574714512 q0,q1,q2,q3,q7,q4,q5; unitary_134450574043728 q7; mcx_vchain_134450574716720 q4,q5,q6,q7,q3; unitary_134450574716192 q7; mcx_vchain_134450574716048 q0,q1,q2,q3,q7,q4,q5; unitary_134450612722416 q7; mcx_vchain_134450574716000 q4,q5,q6,q7,q3; unitary_134450573824784 q7; mcx_vchain_134450574719696 q0,q1,q2,q6,q3; unitary_134450572755840 q6; mcx_vchain_134450574719408 q3,q4,q5,q6,q2; unitary_134450572764336 q6; mcx_vchain_134450574718784 q0,q1,q2,q6,q3; unitary_134450574039456 q6; mcx_vchain_134450574719504 q3,q4,q5,q6,q2; unitary_134450572764960 q6; mcx_vchain_134450572755168 q0,q1,q2,q5,q3; unitary_134450572766400 q5; ccx q3,q4,q5; unitary_134450572767312 q5; mcx_vchain_134450574720944 q0,q1,q2,q5,q3; unitary_134450572768560 q5; ccx q3,q4,q5; unitary_134450572769424 q5; ccx q0,q1,q4; unitary_134450574036720 q4; ccx q2,q3,q4; unitary_134450572766544 q4; ccx q0,q1,q4; unitary_134450572768128 q4; ccx q2,q3,q4; unitary_134450572769712 q4; ccx q0,q1,q3; unitary_134450572770096 q3; cx q2,q3; unitary_134450572770912 q3; ccx q0,q1,q3; unitary_134450572918960 q3; cx q2,q3; unitary_134450572771104 q3; cx q0,q2; unitary_134450572758096 q2; cx q1,q2; unitary_134450572920496 q2; cx q0,q2; unitary_134450572920160 q2; cx q1,q2; unitary_134450572921072 q2; crz(pi/512) q0,q1; p(pi/1024) q0; }
gate mcx_vchain_134450572925968 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450573051472 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450572926112 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450572934368 q0 { u(0,-7*pi/8,9*pi/8) q0; }
gate mcx_vchain_134450572928128 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450572931152 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450572927744 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450572925056 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450572927840 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450572926592 q0 { u(0,-pi/16,-pi/16) q0; }
gate mcx_vchain_134450572927936 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450573053056 q0 { u(0,-15*pi/16,3.3379421944391554) q0; }
gate mcx_vchain_134450572924240 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450574044784 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450572928608 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450572932064 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450572929088 q0,q1,q2,q3,q4,q5,q6 { ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; ccx q3,q6,q4; h q6; t q6; cx q2,q6; tdg q6; cx q5,q6; h q5; t q5; cx q0,q5; tdg q5; cx q1,q5; t q5; cx q0,q5; tdg q5; h q5; cx q5,q6; t q6; cx q2,q6; tdg q6; h q6; }
gate unitary_134450573054064 q0 { u(0,-pi/32,-pi/32) q0; }
gate mcx_vchain_134450572929184 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450573055600 q0 { u(0,-3.043417883165112,3.2397674240144743) q0; }
gate mcx_vchain_134450572919392 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450573056992 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450572921792 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450572930000 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450572921120 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450573053920 q0 { u(0,-pi/64,-pi/64) q0; }
gate mcx_vchain_134450572921168 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450573059536 q0 { u(0,-3.0925052683774528,3.1906800388021335) q0; }
gate mcx_vchain_134450572931056 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450573060736 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450573061792 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate mcx_vchain_134450572930816 q0,q1,q2,q3,q4 { h q3; p(pi/8) q0; p(pi/8) q1; p(pi/8) q2; p(pi/8) q3; cx q0,q1; p(-pi/8) q1; cx q0,q1; cx q1,q2; p(-pi/8) q2; cx q0,q2; p(pi/8) q2; cx q1,q2; p(-pi/8) q2; cx q0,q2; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q1,q3; p(pi/8) q3; cx q2,q3; p(-pi/8) q3; cx q0,q3; h q3; }
gate unitary_134450574033888 q0 { u(0,-pi/128,-pi/128) q0; }
gate unitary_134450573061552 q0 { u(0,-3.117048960983623,3.1661363461959633) q0; }
gate unitary_134450573060880 q0 { u(0,-pi/256,-pi/256) q0; }
gate unitary_134450573062896 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate unitary_134450573063280 q0 { u(0,-pi/256,-pi/256) q0; }
gate unitary_134450573063952 q0 { u(0,-3.129320807286708,3.153864499892878) q0; }
gate unitary_134450573064528 q0 { u(0,-pi/512,-pi/512) q0; }
gate unitary_134450574037584 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate unitary_134450573057472 q0 { u(0,-pi/512,-pi/512) q0; }
gate unitary_134450573058144 q0 { u(0,-3.1354567304382504,3.147728576741336) q0; }
gate unitary_134450573058480 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate unitary_134450573279456 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate unitary_134450573279936 q0 { u(0,-pi/1024,-pi/1024) q0; }
gate unitary_134450573281568 q0 { u(0,-3.138524692014022,3.1446606151655643) q0; }
gate mcphase_134450572761552(param0) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9 { mcx_vchain q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary q9; mcx_vchain_134450572925968 q5,q6,q7,q8,q9,q3,q4; unitary_134450573051472 q9; mcx_vchain q0,q1,q2,q3,q4,q9,q5,q6,q7; unitary q9; mcx_vchain_134450572926112 q5,q6,q7,q8,q9,q3,q4; unitary_134450572934368 q9; mcx_vchain_134450572928128 q0,q1,q2,q3,q8,q4,q5; unitary_134450572931152 q8; mcx_vchain_134450572927744 q4,q5,q6,q7,q8,q2,q3; unitary_134450572925056 q8; mcx_vchain_134450572927840 q0,q1,q2,q3,q8,q4,q5; unitary_134450572926592 q8; mcx_vchain_134450572927936 q4,q5,q6,q7,q8,q2,q3; unitary_134450573053056 q8; mcx_vchain_134450572924240 q0,q1,q2,q3,q7,q4,q5; unitary_134450574044784 q7; mcx_vchain_134450572928608 q4,q5,q6,q7,q3; unitary_134450572932064 q7; mcx_vchain_134450572929088 q0,q1,q2,q3,q7,q4,q5; unitary_134450573054064 q7; mcx_vchain_134450572929184 q4,q5,q6,q7,q3; unitary_134450573055600 q7; mcx_vchain_134450572919392 q0,q1,q2,q6,q3; unitary_134450573056992 q6; mcx_vchain_134450572921792 q3,q4,q5,q6,q2; unitary_134450572930000 q6; mcx_vchain_134450572921120 q0,q1,q2,q6,q3; unitary_134450573053920 q6; mcx_vchain_134450572921168 q3,q4,q5,q6,q2; unitary_134450573059536 q6; mcx_vchain_134450572931056 q0,q1,q2,q5,q3; unitary_134450573060736 q5; ccx q3,q4,q5; unitary_134450573061792 q5; mcx_vchain_134450572930816 q0,q1,q2,q5,q3; unitary_134450574033888 q5; ccx q3,q4,q5; unitary_134450573061552 q5; ccx q0,q1,q4; unitary_134450573060880 q4; ccx q2,q3,q4; unitary_134450573062896 q4; ccx q0,q1,q4; unitary_134450573063280 q4; ccx q2,q3,q4; unitary_134450573063952 q4; ccx q0,q1,q3; unitary_134450573064528 q3; cx q2,q3; unitary_134450574037584 q3; ccx q0,q1,q3; unitary_134450573057472 q3; cx q2,q3; unitary_134450573058144 q3; cx q0,q2; unitary_134450573058480 q2; cx q1,q2; unitary_134450573279456 q2; cx q0,q2; unitary_134450573279936 q2; cx q1,q2; unitary_134450573281568 q2; crz(pi/256) q0,q1; p(pi/512) q0; }
gate mcx q0,q1,q2,q3,q4,q5,q6,q7,q8,q9 { h q9; mcphase_134450572761552(pi) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9; h q9; }
gate gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { mcphase(pi) q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; h q9; h q8; h q7; h q6; h q5; h q4; h q3; h q2; h q1; h q0; x q0; x q1; x q2; x q3; x q4; x q5; x q6; x q7; x q8; x q9; h q9; mcx q0,q1,q2,q3,q4,q5,q6,q7,q8,q9; h q9; x q0; x q1; x q2; x q3; x q4; x q5; x q6; x q7; x q8; x q9; h q0; h q1; h q2; h q3; h q4; h q5; h q6; h q7; h q8; h q9; }
gate gate_Q_134450574708752 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450572769280 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450574709856 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450573054832 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450573065920 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450572919680 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450573055024 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450610153248 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450572924720 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450573058048 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450573282960 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450573286752 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450573288864 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450573287088 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450573290592 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450573294480 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450573294816 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450573609296 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450574714800 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450573608336 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450573613472 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450573616208 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450573616544 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450573620528 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
gate gate_Q_134450573615248 q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10 { gate_Q q0,q1,q2,q3,q4,q5,q6,q7,q8,q9,q10; }
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
h q[7];
h q[8];
h q[9];
x flag[0];
gate_Q_134450574708752 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450572769280 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450574709856 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450573054832 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450573065920 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450572919680 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450573055024 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450610153248 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450572924720 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450573058048 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450573282960 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450573286752 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450573288864 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450573287088 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450573290592 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450573294480 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450573294816 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450573609296 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450574714800 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450573608336 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450573613472 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450573616208 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450573616544 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450573620528 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
gate_Q_134450573615248 q[0],q[1],q[2],q[3],q[4],q[5],q[6],q[7],q[8],q[9],flag[0];
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