#########################################################################################################################
#### glue security group
#########################################################################################################################

# The following ingress rule is configured to allow all traffic (protocol = "-1") from itself (self = true).
# This means any resource within this security group can communicate with any other resource also associated with this security group on any port

resource "aws_security_group" "glue_security_group" {
  name        = "glue-job-sg"
  description = "Security group for AWS Glue Job"
  vpc_id      = "vpc-07249ecda30d27bcf"

  # Ingress rule to allow all traffic from itself (self = true)
  ingress {
    from_port = 0
    to_port   = 0
    protocol  = "-1"
    self      = true
  }

  # Egress rule to allow all traffic from itself (self = true)
  egress {
    from_port = 0
    to_port   = 0
    protocol  = "-1"
    self      = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"] # Allow all outbound traffic
  }


  tags = {
    Name = "Glue Job Security Group"
  }
}

# Outputs the security group ID for reference
output "glue_security_group_id" {
  value = aws_security_group.glue_security_group.id
}


#########################################################################################################################
#### redshift security group allow ingress from glue security group
#########################################################################################################################

resource "aws_security_group_rule" "redshift_ingress_from_glue" {
  type                     = "ingress"
  from_port                = 5439
  to_port                  = 5439
  protocol                 = "tcp"
  security_group_id        = "sg-057c3818d10d6f9b4"
  source_security_group_id = aws_security_group.glue_security_group.id
  description              = "Allow Redshift access from AWS Glue"
}

