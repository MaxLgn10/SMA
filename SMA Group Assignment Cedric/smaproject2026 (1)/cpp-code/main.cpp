//
//  main.cpp
//  projestSMA
//
//  Created by Tine Meersman on 09/02/2022.
//  Copyright © 2022 Tine Meersman. All rights reserved.
//

#include <iostream>

#include "Simulation.hpp"

int main(int argc, const char * argv[]) {
    simulation *sim = new simulation;
    sim->runSimulations();
}
