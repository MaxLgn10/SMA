//
//  Procedure.cpp
//  MarkovChain - Galton-Watson
//
//  Created by Broos  Maenhout on 22/09/2017.
//  Copyright © 2017 Broos  Maenhout. All rights reserved.
//

#include "general.h"
#include <unistd.h>


personnel::personnel()
{
    
    
}

personnel::~personnel()
{
    
    
}

void personnel::procedure()
{
    // Open output file
    strcpy(naam, "/Users/maximilianlangenau/CLionProjects/Exercise12_Kids_Line/Output_Exercise12.txt");
    file1 = fopen(naam, "w");
    fprintf(file1, "Run\tSuccess\tRunning_avg\n");

    init();

    for (i0 = 0; i0 < number_runs; i0++)  // Loop over 10.000 trials
    {
        // STEP 1: Fill stack with [0,1,2,3,4,5]
        // 0 = first child alphabetically, 1 = second, etc.
        for (i1 = 0; i1 < 6; i1++)
            stack[i1] = i1;

        // STEP 2: Generate a random order of the 6 children
        for (i1 = 0; i1 < 6; i1++)
        {
            i2 = rand() % (6 - i1);       // Pick a random index from remaining children
            order[i1] = stack[i2];        // Place selected child at current position

            for (int i3 = i2; i3 < 6 - i1 - 1; i3++)  // Remove selected child from stack
                stack[i3] = stack[i3 + 1];
        }

        // STEP 3: Check if the order equals [0,1,2,3,4,5] (i.e. alphabetical order)
        i2 = 0;
        for (i1 = 0; i1 < 6; i1++)
        {
            if (order[i1] == i1) i2++;
            else break;
        }
        if (i2 == 6) count_success++;  // All 6 positions correct -> success

        // STEP 4: Compute and print running average
        running_average = (float) count_success / (i0 + 1);
        printf("Run\t%d\tSuccess\t%d\tRunning_avg\t%f\n", i0, count_success, running_average);
        fprintf(file1, "%d\t%d\t%f\n", i0, count_success, running_average);
    }

    // Compute final probability estimate
    average = (float) count_success / number_runs;
    fprintf(file1, "TOTAL\t%f\n", average);
    printf("Probability: %f\n", average);

    fclose(file1);
}

void personnel::init()
{
    srand(time(NULL));   // Set random seed
    number_runs = 10000; // Number of simulation trials
    count_success = 0;   // Counter for successful (alphabetical) orderings
    average = 0;         // Final probability estimate
}