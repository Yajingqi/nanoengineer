
#include "simulator.h"

// incremented each time either the potential or gradient is
// calculated.  Used to match values in bond->valid to determine the
// need to recalculate bond->inverseLength and bond->rUnit.
//
// This is the same as setting bond->valid to 0 for each bond,
// checking for non-zero, and setting to non-zero when calculated.  It
// doesn't require the reset loop at the start of each calculation,
// though.
//
// Probably should allow the use of the same serial number for back to
// back calls to potential and gradient using the same positions.  But
// then we'd have to save r and rSquared as well.
static int validSerial = 0;

// presumes that updateVanDerWaals() has been called already.
static void
setRUnit(struct xyz *position, struct bond *b, double *pr)
{
  struct xyz rv;
  double r;
  double rSquared;

  // rv points from a1 to a2
  vsub2(rv, position[b->a2->index], position[b->a1->index]);
  rSquared = vdot(rv, rv);
  r = sqrt(rSquared);
  if (r < 0.001) {
    // atoms are on top of each other
    b->inverseLength = 1000;
    vsetc(b->rUnit, 1.0);
  } else {
    b->inverseLength = 1.0 / r;
    vmul2c(b->rUnit, rv, b->inverseLength); /* unit vector along r from a1 to a2 */
  }
  if (pr) {
    *pr = r;
  }
  b->valid = validSerial;
}

// note: the first two parameters are only used for error processing...
// result in aJ (1e-18 J)
double
stretchPotential(struct part *p, struct stretch *stretch, struct bondStretch *stretchType, double r)
{
  int k;
  double potential;

  /* interpolation */
  double *t1;
  double *t2;
  double start;
  double scale;

  struct interpolationTable *iTable;

  // table lookup equivalent to: potential = potentialLippincottMorse(rSquared);
  iTable = &stretchType->potentialLippincottMorse;
  start = iTable->start;
  scale = iTable->scale;
  t1 = iTable->t1;
  t2 = iTable->t2;
  k = (int)(r - start) / scale;
  if (k < 0) {
    if (!ToMinimize && DEBUG(D_TABLE_BOUNDS) && stretch) { //linear
      fprintf(stderr, "stretch: low --");
      printStretch(stderr, p, stretch);
    }
    potential = t1[0] + r * t2[0];
  } else if (k >= TABLEN) {
    if (ToMinimize) { // extend past end of table using a polynomial
      // XXX switch the following to use Horner's method:
      potential = stretchType->potentialExtensionA
        + stretchType->potentialExtensionB * r
        + stretchType->potentialExtensionC * r * r
        + stretchType->potentialExtensionD * r * r * r;
      //potential = stretchType->potentialExtensionStiffness * r * r
      //          + stretchType->potentialExtensionIntercept;
      //potential = t1[TABLEN-1]+ ((TABLEN-1) * scale + start) * t2[TABLEN-1];
    } else {
      potential=0.0;
      if (DEBUG(D_TABLE_BOUNDS) && stretch) {
        fprintf(stderr, "stretch: high --");
        printStretch(stderr, p, stretch);
      }
    }
  } else if (DirectEvaluate) {
    potential = potentialLippincottMorse(r, stretchType);
  } else {
    potential = t1[k] + r * t2[k];
  }
  return potential;
}

// result in pN (1e-12 J/m)
double
stretchGradient(struct part *p, struct stretch *stretch, struct bondStretch *stretchType, double r)
{
  int k;
  double gradient;

  /* interpolation */
  double *t1;
  double *t2;
  double start;
  double scale;

  struct interpolationTable *iTable;

    // table lookup equivalent to: gradient = gradientLippincottMorse(r);
    // Note:  this points uphill, toward higher potential values.
    iTable = &stretchType->gradientLippincottMorse;
    start = iTable->start;
    scale = iTable->scale;
    t1 = iTable->t1;
    t2 = iTable->t2;
    k = (int)(r - start) / scale;
    if (k < 0) {
      if (!ToMinimize && DEBUG(D_TABLE_BOUNDS) && stretch) { //linear
        fprintf(stderr, "stretch: low --");
        printStretch(stderr, p, stretch);
      }
      gradient = t1[0] + r * t2[0];
    } else if (k >= TABLEN) {
      if (ToMinimize) { // extend past end of table using a polynomial
        // XXX switch the following to use Horner's method:
        gradient = stretchType->potentialExtensionB
          + stretchType->potentialExtensionC * r * 2.0
          + stretchType->potentialExtensionD * r * r * 3.0;
        gradient *= DR ;
        //gradient = 2.0 * stretchType->potentialExtensionStiffness * r;
        //gradient = t1[TABLEN-1]+ ((TABLEN-1) * scale + start) * t2[TABLEN-1];
      } else {
        gradient=0.0;
        if (DEBUG(D_TABLE_BOUNDS) && stretch) {
          fprintf(stderr, "stretch: high --");
          printStretch(stderr, p, stretch);
        }
      }
    } else if (DirectEvaluate) {
      gradient = gradientLippincottMorse(r, stretchType);
    } else {
      gradient = t1[k] + r * t2[k];
    }
    return gradient;
}

// result in aJ (1e-18 J)
double
vanDerWaalsPotential(struct part *p, struct vanDerWaals *vdw, struct vanDerWaalsParameters *parameters, double r)
{
  double potential;
  int k;
  double *t1;
  double *t2;
  double start;
  double scale;
  struct interpolationTable *iTable;
  
  /* table setup  */
  iTable = &parameters->potentialBuckingham;
  start = iTable->start;
  scale = iTable->scale;
  t1 = iTable->t1;
  t2 = iTable->t2;

  k=(int)(r - start) / scale;
  if (k < 0) {
    if (!ToMinimize && DEBUG(D_TABLE_BOUNDS)) { //linear
      fprintf(stderr, "vdW: off table low -- r=%.2f \n",  r);
      printVanDerWaals(stderr, p, vdw);
    }
    k=0;
    potential = t1[k] + r * t2[k];
  } else if (DirectEvaluate) {
    potential = potentialBuckingham(r, parameters);
  } else if (k>=TABLEN) {
    potential = 0.0;
  } else {
    potential = t1[k] + r * t2[k];
  }
  return potential;
}

// result in pN (1e-12 J/m), but divided by the radius vector
double
vanDerWaalsGradient(struct part *p, struct vanDerWaals *vdw, struct vanDerWaalsParameters *parameters, double r)
{
  double gradient;
  int k;
  double *t1;
  double *t2;
  double start;
  double scale;
  struct interpolationTable *iTable;
      
  /* table setup  */
  iTable = &parameters->gradientBuckingham;
  start = iTable->start;
  scale = iTable->scale;
  t1 = iTable->t1;
  t2 = iTable->t2;
					
  k=(int)(r - start) / scale;
  if (k < 0) {
    if (!ToMinimize && DEBUG(D_TABLE_BOUNDS)) { //linear
      fprintf(stderr, "vdW: off table low -- r=%.2f \n",  r);
      printVanDerWaals(stderr, p, vdw);
    }
    k=0;
    gradient = t1[k] + r * t2[k];
  } else if (DirectEvaluate) {
    gradient = gradientBuckingham(r, parameters);
  } else if (k>=TABLEN) {
    gradient = 0.0;
  } else {
    gradient = t1[k] + r * t2[k];
  }
  return gradient;
}

// result in aJ (1e-18 J)
double
calculatePotential(struct part *p, struct xyz *position)
{
  int j;
  double rSquared;
  struct xyz v1;
  struct xyz v2;
  double z;
  double theta;
  double dTheta;
  double ff;
  double potential = 0.0;

  struct stretch *stretch;
  struct bond *bond;
  struct bond *bond1;
  struct bond *bond2;
  struct bend *bend;
  struct bendData *bType;
  struct vanDerWaals *vdw;
  struct xyz rv;
  double r;

  validSerial++;

  if (!DEBUG(D_SKIP_STRETCH)) { // -D6
    for (j=0; j<p->num_stretches; j++) {
      stretch = &p->stretches[j];
      bond = stretch->b;

      // we presume here that rUnit is invalid, and we need rSquared
      // anyway.
      setRUnit(position, bond, &r);
      potential += stretchPotential(p, stretch, stretch->stretchType, r);
    }
  }
			
  /* now the potential for each bend */

  if (!DEBUG(D_SKIP_BEND)) { // -D7
    for (j=0; j<p->num_bends; j++) {
      bend = &p->bends[j];

      bond1 = bend->b1;
      bond2 = bend->b2;

      // Update rUnit for both bonds, if necessary.  Note that we
      // don't need r or rSquared here.
      if (bond1->valid != validSerial) {
        setRUnit(position, bond1, NULL);
      }
      if (bond2->valid != validSerial) {
        setRUnit(position, bond2, NULL);
      }
      
      // v1, v2 are the unit vectors FROM the central atom TO the
      // neighbors.  Reverse them if we have to.
      if (bend->dir1) {
        vsetn(v1, bond1->rUnit);
      } else {
        vset(v1, bond1->rUnit);
      }
      if (bend->dir2) {
        vsetn(v2, bond2->rUnit);
      } else {
        vset(v2, bond2->rUnit);
      }


#define ACOS_POLY_A -0.0820599
#define ACOS_POLY_B  0.142376
#define ACOS_POLY_C -0.137239
#define ACOS_POLY_D -0.969476

      z = vlen(vsum(v1, v2));
      // this is the equivalent of theta=arccos(z);
      theta = Pi + z * (ACOS_POLY_D +
                   z * (ACOS_POLY_C +
                   z * (ACOS_POLY_B +
                   z *  ACOS_POLY_A   )));

      // bType->kb in yJ/rad^2 (1e-24 J/rad^2)
      bType = bend->bendType;
      dTheta = (theta - bType->theta0);
      ff = 0.5 * dTheta * dTheta * bType->kb;
      // ff is in yJ (1e-24 J), potential in aJ (1e-18 J)
      potential += ff * 1e-6;
    }
  }

  if (!DEBUG(D_SKIP_VDW)) { // -D9
    /* do the van der Waals/London forces */
    for (j=0; j<p->num_vanDerWaals; j++) {
      vdw = p->vanDerWaals[j];

      // The vanDerWaals array changes over time, and might have
      // NULL's in it as entries are deleted.
      if (vdw == NULL) {
        continue;
      }
      
      vsub2(rv, position[vdw->a1->index], position[vdw->a2->index]);
      rSquared = vdot(rv, rv);
      r = sqrt(rSquared);
      potential += vanDerWaalsPotential(p, vdw, vdw->parameters, r);
    }
  }
  
  return potential;
}

// result placed in force is in pN (1e-12 J/m)
void
calculateGradient(struct part *p, struct xyz *position, struct xyz *force)
{
  int j;
  double rSquared;
  double gradient;
  struct xyz v1;
  struct xyz v2;
  double z;
  double theta;
  double ff;

  struct stretch *stretch;
  struct bond *bond;
  struct bond *bond1;
  struct bond *bond2;
  struct bend *bend;
  struct bendData *bType;
  double torque;
  struct vanDerWaals *vdw;
  struct xyz rv;
  struct xyz q1;
  struct xyz q2;
  struct xyz foo;
  struct xyz axis;
  struct xyz f;
  double r;

  validSerial++;
    
  /* clear force vectors */
  for (j=0; j<p->num_atoms; j++) {
    vsetc(force[j], 0.0);
  }
  
  if (!DEBUG(D_SKIP_STRETCH)) { // -D6
    for (j=0; j<p->num_stretches; j++) {
      stretch = &p->stretches[j];
      bond = stretch->b;

      // we presume here that rUnit is invalid, and we need r anyway
      setRUnit(position, bond, &r);

      gradient = stretchGradient(p, stretch, stretch->stretchType, r);
      // rUnit points from a1 to a2; F = -gradient
      vmul2c(f, bond->rUnit, gradient);
      vadd(force[bond->a1->index], f);
      vsub(force[bond->a2->index], f);
      if (DEBUG(D_MINIMIZE_GRADIENT_MOVIE_DETAIL)) { // -D5
        writeSimpleForceVector(position, bond->a1->index, &f, 1); // red
        vmulc(f, -1.0);
        writeSimpleForceVector(position, bond->a2->index, &f, 1); // red
      }
    }
  }

  if (!DEBUG(D_SKIP_BEND)) { // -D7
    /* now the forces for each bend */
    for (j=0; j<p->num_bends; j++) {
      bend = &p->bends[j];

      bond1 = bend->b1;
      bond2 = bend->b2;

      // Update rUnit for both bonds, if necessary.  Note that we
      // don't need r or rSquared here.
      if (bond1->valid != validSerial) {
        setRUnit(position, bond1, NULL);
      }
      if (bond2->valid != validSerial) {
        setRUnit(position, bond2, NULL);
      }
      
      // v1, v2 are the unit vectors FROM the central atom TO the
      // neighbors.  Reverse them if we have to.
      if (bend->dir1) {
        vsetn(v1, bond1->rUnit);
      } else {
        vset(v1, bond1->rUnit);
      }
      if (bend->dir2) {
        vsetn(v2, bond2->rUnit);
      } else {
        vset(v2, bond2->rUnit);
      }

      // XXX figure out how close we can get / need to get
      // apply no force if v1 and v2 are close to being linear
#define COLINEAR 1e-8
      z = vlen(vsum(v1, v2));
      // this is the equivalent of theta=arccos(z);
      theta = Pi + z * (ACOS_POLY_D +
                   z * (ACOS_POLY_C +
                   z * (ACOS_POLY_B +
                   z *  ACOS_POLY_A   )));

      v2x(foo, v1, v2);       // foo = v1 cross v2
      if (vlen(foo) < COLINEAR) {
        // v1 and v2 are very close to colinear.  We can pick any
        // vector orthogonal to either one.  First we try v1 x (1, 0,
        // 0).  If v1 is colinear with the x axis, then in can't be
        // colinear with the y axis too, so we use v1 x (0, 1, 0) in
        // that case.
        axis.x = 1;
        axis.y = 0;
        axis.z = 0;
        v2x(foo, v1, axis);
        if (vlen(foo) < COLINEAR) {
          axis.x = 0;
          axis.y = 1;
          v2x(foo, v1, axis);
        }
      }
        
      //foo = uvec(foo);        // hmmm... not sure why this has to be a unit vector.
      q1 = uvec(vx(v1, foo)); // unit vector perpendicular to v1 in plane of v1 and v2
      q2 = uvec(vx(foo, v2)); // unit vector perpendicular to v2 in plane of v1 and v2

      // bType->kb in yJ/rad^2 (1e-24 J/rad^2)
      bType = bend->bendType;
      // torque in yJ/rad
      torque = (theta - bType->theta0) * bType->kb;
      // inverseLength is pm/rad
      // ff is yJ/pm (1e-24 J / 1e-12 m) or 1e-12 J/m or pN
      ff = torque * bond1->inverseLength;
      vmulc(q1, ff);
      ff = torque * bond2->inverseLength;
      vmulc(q2, ff);

      vsub(force[bend->ac->index], q1);
      vadd(force[bend->a1->index], q1);
      vsub(force[bend->ac->index], q2);
      vadd(force[bend->a2->index], q2);
      if (DEBUG(D_MINIMIZE_GRADIENT_MOVIE_DETAIL)) { // -D5
        writeSimpleForceVector(position, bend->a1->index, &q1, 3); // blue
        vmulc(q1, -1.0);
        writeSimpleForceVector(position, bend->ac->index, &q1, 2); // green
        writeSimpleForceVector(position, bend->a2->index, &q2, 3); // blue
        vmulc(q2, -1.0);
        writeSimpleForceVector(position, bend->ac->index, &q2, 2); // green
      }
    }
  }

  if (!DEBUG(D_SKIP_VDW)) { // -D9
    /* do the van der Waals/London forces */
    for (j=0; j<p->num_vanDerWaals; j++) {
      vdw = p->vanDerWaals[j];

      // The vanDerWaals array changes over time, and might have
      // NULL's in it as entries are deleted.
      if (vdw == NULL) {
        continue;
      }
      
      vsub2(rv, position[vdw->a1->index], position[vdw->a2->index]);
      rSquared = vdot(rv, rv);
      r = sqrt(rSquared);
    
      gradient = vanDerWaalsGradient(p, vdw, vdw->parameters, r);
    
      vmul2c(f, rv, gradient);
      vadd(force[vdw->a1->index], f);
      vsub(force[vdw->a2->index], f);
    }
  }
}
