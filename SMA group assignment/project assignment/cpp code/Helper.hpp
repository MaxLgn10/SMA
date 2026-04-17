//
//  Helper.hpp
//  projestSMA
//
//  Created by Tine Meersman on 09/02/2022.
//  Copyright © 2022 Tine Meersman. All rights reserved.
//

#ifndef Helper_hpp
#define Helper_hpp

double Exponential_distribution(double lambda);
int Poisson_distribution(double lambda);
double Normal_distribution(double mean, double stdev);
int Bernouilli_distribution(double prob);
int Uniform_distribution(double a, double b);
int Triangular_distribution(int a, int b, int c);



#endif /* Helper_hpp */
